import argparse
import json
import time
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser(description="Preview/crop HDMI DVR mosaic")
    parser.add_argument("--config", required=True)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)

    source = cfg.get("input", "/dev/video0")
    cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open capture input: {source}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cfg.get("frame_width", 1920)))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cfg.get("frame_height", 1080)))
    cap.set(cv2.CAP_PROP_FPS, float(cfg.get("fps", 10)))

    out_dir = Path(cfg.get("output_dir", "/tmp/analog_dvr_crops"))
    out_dir.mkdir(parents=True, exist_ok=True)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("capture read failed")
            time.sleep(1)
            continue

        for cam in cfg.get("cameras", []):
            name = cam["name"]
            x, y, w, h = int(cam["x"]), int(cam["y"]), int(cam["w"]), int(cam["h"])
            crop = frame[y:y+h, x:x+w]
            if crop.size == 0:
                print(f"{name}: empty crop")
                continue
            cv2.imwrite(str(out_dir / f"{name}.jpg"), crop)
            if args.show:
                cv2.imshow(name, crop)

        if args.show and cv2.waitKey(1) & 0xFF == ord("q"):
            break
        time.sleep(0.1)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
