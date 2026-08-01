import json
import threading
from pathlib import Path
from typing import Any

from agent.config import DEFAULT_CONFIG_PATH, load_config, stream_name
from agent.dvr_rtsp import find_working_url
from agent.logging_config import logger
from agent.worker import ChannelWorker


class AnalogDvrRuntime:
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.lock = threading.RLock()
        self.workers: list[ChannelWorker] = []
        self.last_probe: list[dict[str, Any]] = []
        self.running = False

    def load(self) -> dict:
        return load_config(self.config_path)

    def save_config(self, config: dict) -> None:
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        tmp.replace(path)
        logger.info("config saved path=%s", path)

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
            results.append({
                "channel": int(channel),
                "stream_name": name,
                "ok": bool(url),
                "selected_url": url,
                "attempts": [
                    {"url": attempt_url, "ok": ok, "output": output}
                    for attempt_url, ok, output in attempts
                ],
            })
        with self.lock:
            self.last_probe = results
        return results

    def start(self) -> dict[str, Any]:
        with self.lock:
            self.stop_locked()
            cfg = self.load()
            media = cfg.get("media") or {}
            probe_results = self.probe()
            for item in probe_results:
                if not item["ok"]:
                    logger.warning("stream=%s skipped; no working RTSP URL", item["stream_name"])
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
                "ok": True,
                "running": self.running,
                "config_path": self.config_path,
                "workers": [worker.status() for worker in self.workers],
                "last_probe": self.last_probe,
            }
