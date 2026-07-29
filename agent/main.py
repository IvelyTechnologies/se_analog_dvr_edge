import argparse
import signal
import time

from agent.config import load_config, stream_name
from agent.dvr_rtsp import find_working_url
from agent.worker import ChannelWorker


def build_publish_url(media: dict, name: str) -> str:
    host = media.get("rtsp_publish_host", "127.0.0.1")
    port = int(media.get("rtsp_publish_port", 8554))
    return f"rtsp://{host}:{port}/{name}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analog DVR edge channel publisher")
    parser.add_argument("--config", help="Config JSON path")
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    dvr = cfg["dvr"]
    candidates = cfg["rtsp_candidates"]
    media = cfg.get("media") or {}
    prefix = cfg["site_prefix"]

    workers = []
    for channel in dvr["channels"]:
        name = stream_name(prefix, int(channel))
        print(f"\n=== channel={channel} stream={name} ===")
        url, attempts = find_working_url(dvr, candidates, int(channel))
        for attempt_url, ok, output in attempts:
            print(("OK   " if ok else "FAIL ") + attempt_url)
            if output:
                print(output)
        if not url:
            print(f"No working RTSP URL for channel {channel}")
            continue
        if args.probe_only:
            continue
        publish_url = build_publish_url(media, name)
        workers.append(ChannelWorker(name, url, publish_url, media))

    if args.probe_only:
        return 0

    if not workers:
        print("No workers started. Check DVR config and RTSP URLs.")
        return 2

    stopping = False

    def handle_signal(_signum, _frame):
        nonlocal stopping
        stopping = True
        for worker in workers:
            worker.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    for worker in workers:
        worker.start()

    while not stopping:
        time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
