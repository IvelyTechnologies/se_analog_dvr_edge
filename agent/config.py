import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = os.environ.get(
    "ANALOG_DVR_CONFIG",
    "/opt/ively/analog-dvr-edge/configs/dvr_channels.json",
)


def load_config(path: str | None = None) -> dict:
    config_path = Path(path or DEFAULT_CONFIG_PATH)
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("site_prefix"):
        raise ValueError("site_prefix is required")
    dvr = cfg.get("dvr") or {}
    if not dvr.get("ip"):
        raise ValueError("dvr.ip is required")
    if not dvr.get("channels"):
        raise ValueError("dvr.channels is required")
    if not cfg.get("rtsp_candidates"):
        raise ValueError("rtsp_candidates is required")
    return cfg


def stream_name(site_prefix: str, channel: int) -> str:
    clean = str(site_prefix).strip().lower().replace(" ", "_")
    return f"{clean}_ch{int(channel)}_low"
