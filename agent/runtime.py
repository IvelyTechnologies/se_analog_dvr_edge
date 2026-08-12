import json
import threading
from pathlib import Path
from typing import Any

from agent.config import DEFAULT_CONFIG_PATH, load_config, stream_name
from agent.dvr_rtsp import find_working_url, redact_rtsp_url
from agent.logging_config import logger
from agent.mediamtx_paths import ensure_publisher_paths
from agent.worker import ChannelWorker


class AnalogDvrRuntime:
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.lock = threading.RLock()
        self.workers: list[ChannelWorker] = []
        self.last_probe: list[dict[str, Any]] = []
        self.running = False
        self.last_start_error: str | None = None

    def load(self) -> dict:
        return load_config(self.config_path)

    def save_config(self, config: dict) -> None:
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
        with self.lock:
            self.stop_locked()
            self.last_start_error = None
            cfg = self.load()
            try:
                added_paths = self._ensure_mediamtx_paths(cfg)
            except Exception as exc:
                self.last_start_error = str(exc)
                logger.exception("could not register MediaMTX publisher paths")
                return self.status()

            if added_paths:
                self.last_start_error = (
                    "MediaMTX paths registered; restart mediamtx, then reload analog-dvr-edge."
                )
                logger.warning("%s paths=%s", self.last_start_error, added_paths)
                return self.status()

            media = cfg.get("media") or {}
            probe_results = self.probe()
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
            logger.info("runtime started workers=%s", len(self.workers))
            return self.status()

    def stop_locked(self) -> None:
        for worker in self.workers:
            worker.stop()
        self.workers = []
        self.running = False

    def stop(self) -> dict[str, Any]:
        with self.lock:
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
