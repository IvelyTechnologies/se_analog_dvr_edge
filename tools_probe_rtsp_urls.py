import argparse
import json
import subprocess
from urllib.parse import quote


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_url(template, dvr, channel):
    return template.format(
        username=quote(str(dvr.get("username", "")), safe=""),
        password=quote(str(dvr.get("password", "")), safe=""),
        ip=dvr.get("ip", ""),
        channel=channel,
    )


def probe(url, timeout=8):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-rtsp_transport", "tcp",
        "-timeout", str(timeout * 1000000),
        "-i", url,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "default=nw=1",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 4)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def main():
    parser = argparse.ArgumentParser(description="Probe DVR per-channel RTSP URLs")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    dvr = cfg["dvr"]
    templates = cfg.get("rtsp_candidates", [])
    channels = dvr.get("channels", [])

    for channel in channels:
        print(f"\nCHANNEL {channel}")
        for template in templates:
            url = format_url(template, dvr, channel)
            code, output = probe(url)
            status = "OK" if code == 0 else f"FAIL exit={code}"
            print(f"{status} {url}")
            if output.strip():
                print(output.strip())
            if code == 0:
                break


if __name__ == "__main__":
    main()
