import json
import threading
from pathlib import Path
from typing import Any

from agent.config import DEFAULT_CONFIG_PATH, load_config, stream_name, validate_config
from agent.dvr_rtsp import find_working_url, redact_rtsp_url
from agent.logging_config import logger
from agent.mediamtx_paths import ensure_mobile_hls_settings, ensure_publisher_paths
from agent.worker import ChannelWorker


class AnalogDvrRuntime:
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.lock = threading.RLock()
        # Startup performs network probes and can take several minutes when a
        # DVR is not configured yet. Serialize starts separately, but never
        # hold the status/config lock during those slow operations.
        self._start_lock = threading.Lock()
        self.workers: list[ChannelWorker] = []
        self.last_probe: list[dict[str, Any]] = []
        self.running = False
        self.last_start_error: str | None = None
        self._stop_event = threading.Event()
        self._recovery_thread: threading.Thread | None = None

    def load(self) -> dict:
        return load_config(self.config_path)

    def save_config(self, config: dict) -> None:
        if not isinstance(config, dict):
            raise ValueError("configuration must be an object")

        # The local setup page never reads the real password back. A blank or
        # masked password means "keep the saved value" during an update.
        previous = self.load()
        dvr = config.setdefault("dvr", {})
        password = str(dvr.get("password") or "").strip()
        if password in {"", "***"}:
            dvr["password"] = (previous.get("dvr") or {}).get("password", "")

        validate_config(config)
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=2)
        temporary.replace(path)
        logger.info("config saved path=%s", path)

    def public_config(self) -> dict:
        """Return configuration without the DVR password."""
        config = json.loads(json.dumps(self.load()))
        dvr = config.get("dvr") or {}
        if dvr.get("password"):
            dvr["password"] = "***"
        return config

    @staticmethod
    def _public_probe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        public: list[dict[str, Any]] = []
        for item in results:
            copy = dict(item)
            copy["selected_url"] = redact_rtsp_url(copy.get("selected_url"))
            copy["attempts"] = [
                {**attempt, "url": redact_rtsp_url(attempt.get("url"))}
                for attempt in item.get("attempts", [])
            ]
            public.append(copy)
        return public

    def public_probe(self) -> list[dict[str, Any]]:
        return self._public_probe_results(self.probe())

    def _ensure_mediamtx_paths(self, config: dict) -> list[str]:
        prefix = config["site_prefix"]
        channels = (config.get("dvr") or {}).get("channels") or []
        return ensure_publisher_paths(
            [stream_name(prefix, int(channel)) for channel in channels],
            config_path=(config.get("mediamtx") or {}).get(
                "config_path", "/opt/ively/mediamtx/mediamtx.yml"
            ),
        )

    def _configure_standalone_mobile_hls(self, config: dict) -> bool:
        """Write HLS settings only when this DVR install explicitly owns them."""
        mediamtx = config.get("mediamtx") or {}
        if not mediamtx.get("manage_hls", False):
            return False
        config_path = mediamtx.get("config_path", "/opt/ively/mediamtx/mediamtx.yml")
        changed = ensure_mobile_hls_settings(
            config_path=config_path,
            segment_duration=mediamtx.get("hls_segment_duration", "2s"),
            segment_count=mediamtx.get("hls_segment_count", 45),
        )
        return changed

    def build_publish_url(self, media: dict, name: str) -> str:
        host = media.get("rtsp_publish_host", "127.0.0.1")
        port = int(media.get("rtsp_publish_port", 8554))
        return f"rtsp://{host}:{port}/{name}"

    def probe(self, channels: list[int] | None = None) -> list[dict[str, Any]]:
        cfg = self.load()
        dvr = cfg["dvr"]
        candidates = cfg["rtsp_candidates"]
        prefix = cfg["site_prefix"]
        results: list[dict[str, Any]] = []

        selected_channels = channels if channels is not None else dvr["channels"]
        for channel in selected_channels:
            name = stream_name(prefix, int(channel))
            logger.info("probing channel=%s stream=%s", channel, name)
            url, attempts = find_working_url(dvr, candidates, int(channel))
            results.append(
                {
                    "channel": int(channel),
                    "stream_name": name,
                    "ok": bool(url),
                    "selected_url": url,
                    "attempts": [
                        {"url": attempt_url, "ok": ok, "output": output}
                        for attempt_url, ok, output in attempts
                    ],
                }
            )
        with self.lock:
            self.last_probe = results
        return results

    def start(self) -> dict[str, Any]:
        with self._start_lock:
            with self.lock:
                self._stop_event.clear()
                self.last_start_error = None
                cfg = self.load()
            try:
                hls_changed = self._configure_standalone_mobile_hls(cfg)
                added_paths = self._ensure_mediamtx_paths(cfg)
            except Exception as exc:
                self.last_start_error = str(exc)
                logger.exception("could not register MediaMTX publisher paths")
                return self.status()

            if hls_changed or added_paths:
                # MediaMTX watches its configuration and applies this update
                # without a process restart. Do not turn a normal initial
                # configuration write into an outage: the publisher workers
                # below retry until the hot-reloaded paths are ready.
                changes: list[str] = []
                if hls_changed:
                    changes.append("HLS settings")
                if added_paths:
                    changes.append(f"publisher paths: {', '.join(added_paths)}")
                logger.info(
                    "MediaMTX configuration updated (%s); starting DVR publishers without restarting MediaMTX.",
                    "; ".join(changes),
                )

            with self.lock:
                self.stop_locked()

            media = cfg.get("media") or {}
            probe_results = self.probe()
            with self.lock:
                # A stop can arrive while a slow DVR probe is running. Do not
                # publish new workers after that explicit stop request.
                if self._stop_event.is_set():
                    return self.status()
                for item in probe_results:
                    if not item["ok"]:
                        logger.warning(
                            "stream=%s skipped; no working RTSP URL", item["stream_name"]
                        )
                        continue
                    publish_url = self.build_publish_url(media, item["stream_name"])
                    worker = ChannelWorker(
                        item["stream_name"],
                        item["selected_url"],
                        publish_url,
                        media,
                    )
                    self.workers.append(worker)
                    worker.start()
                self.running = bool(self.workers)
                missing_channels = [item["channel"] for item in probe_results if not item["ok"]]
                if not self.running:
                    self.last_start_error = "No DVR channel is reachable yet; retrying automatically."
                    self._schedule_recovery_locked()
                elif missing_channels:
                    self.last_start_error = (
                        f"DVR channels {', '.join(map(str, missing_channels))} are unavailable; "
                        "retrying automatically."
                    )
                    self._schedule_recovery_locked()
                logger.info("runtime started workers=%s", len(self.workers))
                return self.status()

    def _schedule_recovery_locked(self) -> None:
        """Retry only missing channels after boot or a DVR/LAN interruption."""
        if self._recovery_thread and self._recovery_thread.is_alive():
            return

        def retry_until_recovered() -> None:
            while not self._stop_event.wait(10):
                if self._recover_missing_channels():
                    logger.info("DVR channel recovery succeeded")
                    return

        self._recovery_thread = threading.Thread(
            target=retry_until_recovered,
            daemon=True,
            name="analog-dvr-recovery",
        )
        self._recovery_thread.start()

    def _recover_missing_channels(self) -> bool:
        """Probe and start only channels that do not already have a worker.

        A power recovery can bring up the Mini PC before the local DVR route is
        usable. Never call ``start()`` here: that would stop healthy streams
        while retrying the one or two channels that lost their initial probe.
        """
        with self._start_lock:
            cfg = self.load()
            dvr = cfg["dvr"]
            prefix = cfg["site_prefix"]
            with self.lock:
                if self._stop_event.is_set():
                    return True
                active_names = {worker.name for worker in self.workers}
                missing_channels = [
                    int(channel)
                    for channel in dvr["channels"]
                    if stream_name(prefix, int(channel)) not in active_names
                ]

            if not missing_channels:
                with self.lock:
                    self.last_start_error = None
                return True

            logger.info("retrying unavailable DVR channels=%s", missing_channels)
            probe_results = self.probe(missing_channels)
            media = cfg.get("media") or {}
            with self.lock:
                if self._stop_event.is_set():
                    return True
                active_names = {worker.name for worker in self.workers}
                for item in probe_results:
                    if not item["ok"] or item["stream_name"] in active_names:
                        continue
                    worker = ChannelWorker(
                        item["stream_name"],
                        item["selected_url"],
                        self.build_publish_url(media, item["stream_name"]),
                        media,
                    )
                    self.workers.append(worker)
                    worker.start()
                    active_names.add(item["stream_name"])
                    logger.info("recovered DVR channel=%s stream=%s", item["channel"], item["stream_name"])

                still_missing = [
                    int(channel)
                    for channel in dvr["channels"]
                    if stream_name(prefix, int(channel)) not in active_names
                ]
                self.running = bool(self.workers)
                if still_missing:
                    self.last_start_error = (
                        f"DVR channels {', '.join(map(str, still_missing))} are unavailable; "
                        "retrying automatically."
                    )
                    return False
                self.last_start_error = None
                return True

    def stop_locked(self) -> None:
        for worker in self.workers:
            worker.stop()
        self.workers = []
        self.running = False

    def stop(self) -> dict[str, Any]:
        with self.lock:
            self._stop_event.set()
            self.stop_locked()
            logger.info("runtime stopped")
            return self.status()

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {
                "ok": not bool(self.last_start_error),
                "running": self.running,
                "last_start_error": self.last_start_error,
                "config_path": self.config_path,
                "workers": [
                    {
                        **worker.status(),
                        "input_url": redact_rtsp_url(worker.status()["input_url"]),
                    }
                    for worker in self.workers
                ],
                "last_probe": self._public_probe_results(self.last_probe),
            }
