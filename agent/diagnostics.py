import shutil
import subprocess
from typing import Any


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_cmd(cmd: list[str], timeout: int = 8) -> dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": r.returncode == 0,
            "exit_code": r.returncode,
            "stdout": (r.stdout or "").strip(),
            "stderr": (r.stderr or "").strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def diagnostics() -> dict[str, Any]:
    return {
        "ffmpeg_available": command_exists("ffmpeg"),
        "ffprobe_available": command_exists("ffprobe"),
        "python": run_cmd(["python3", "--version"]),
        "ffmpeg": run_cmd(["ffmpeg", "-version"]),
        "mediamtx_service": run_cmd(["systemctl", "is-active", "mediamtx"], timeout=4),
        "analog_dvr_edge_service": run_cmd(["systemctl", "is-active", "analog-dvr-edge"], timeout=4),
    }
