import json
import subprocess
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

    @staticmethod
    def _restart_mediamtx() -> None:
        """Reload MediaMTX once after standalone settings and paths are written."""
        subprocess.run(
            ["systemctl", "restart", "mediamtx"],
            check=True,
            timeout=30,
            capture_output=True,
            text=True,
        )

    def build_publish_url(self, media: dict, name: str) -> str:
        host = media.get("rtsp_publish_host", "127.0.0.1")
        port = int(media.get("rtsp_publish_port", 8554))
        return f"rtsp://{host}:{port}/{name}"

    def probe(self) -> list[dict[str, Any]]:
        cfg = self.load()
        dvr = cfg["dvr"]
        candidates = cfg["rtsp_candidates"]
        prefix = cfg["site_prefix"]
        results: list[dict[str, Any]] = []

        for channel in dvr["channels"]:
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
                self.stop_locked()
                self.last_start_error = None
                cfg = self.load()
            try:
                hls_changed = self._configure_standalone_mobile_hls(cfg)
                added_paths = self._ensure_mediamtx_paths(cfg)
                standalone_hls = bool((cfg.get("mediamtx") or {}).get("manage_hls", False))
                if standalone_hls and (hls_changed or added_paths):
                    # Write both settings and paths before the single restart;
                    # otherwise first boot can load HLS settings without the
                    # new DVR publisher paths.
                    self._restart_mediamtx()
                    logger.info(
                        "restarted MediaMTX after standalone DVR configuration hls_changed=%s paths=%s",
                        hls_changed,
                        added_paths,
                    )
            except Exception as exc:
                self.last_start_error = str(exc)
                logger.exception("could not register MediaMTX publisher paths")
                return self.status()

            if added_paths:
                if standalone_hls:
                    logger.info("MediaMTX DVR publisher paths activated. paths=%s", added_paths)
                else:
                    # In a shared NVR + DVR install, Ively Edge owns the
                    # MediaMTX lifecycle, so do not restart it from here.
                    logger.warning(
                        "MediaMTX paths registered; DVR publishers will retry until MediaMTX reloads. paths=%s",
                        added_paths,
                    )

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
                if not self.running:
                    self.last_start_error = "No DVR channel is reachable yet; retrying automatically."
                    self._schedule_recovery_locked()
                logger.info("runtime started workers=%s", len(self.workers))
                return self.status()

    def _schedule_recovery_locked(self) -> None:
        """Retry discovery after boot when the DVR network is not ready yet."""
        if self._recovery_thread and self._recovery_thread.is_alive():
            return

        def retry_until_running() -> None:
            while not self._stop_event.wait(10):
                result = self.start()
                if result["running"]:
                    logger.info("DVR recovery succeeded")
                    return

        self._recovery_thread = threading.Thread(
            target=retry_until_running,
            daemon=True,
            name="analog-dvr-recovery",
        )
        self._recovery_thread.start()

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
