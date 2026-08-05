import subprocess
from urllib.parse import quote, urlsplit, urlunsplit


def redact_rtsp_url(url: str | None) -> str | None:
    """Hide DVR credentials before returning a URL through the local API."""
    if not url:
        return url
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url
    credentials, host = parts.netloc.rsplit("@", 1)
    username = credentials.split(":", 1)[0]
    return urlunsplit((parts.scheme, f"{username}:***@{host}", parts.path, parts.query, parts.fragment))


def format_rtsp_url(template: str, dvr: dict, channel: int) -> str:
    return template.format(
        username=quote(str(dvr.get("username", "")), safe=""),
        password=quote(str(dvr.get("password", "")), safe=""),
        ip=str(dvr.get("ip", "")),
        channel=int(channel),
    )


def probe_rtsp(url: str, timeout_sec: int = 8) -> tuple[bool, str]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-rtsp_transport", "tcp",
        "-timeout", str(timeout_sec * 1_000_000),
        "-i", url,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "default=nw=1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 4)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return result.returncode == 0, output


def find_working_url(dvr: dict, candidates: list[str], channel: int) -> tuple[str | None, list[tuple[str, bool, str]]]:
    attempts = []
    for template in candidates:
        url = format_rtsp_url(template, dvr, channel)
        ok, output = probe_rtsp(url)
        attempts.append((url, ok, output))
        if ok:
            return url, attempts
    return None, attempts
