import shlex


def ffmpeg_publish_command(input_url: str, publish_url: str, media: dict) -> list[str]:
    width = str(media.get("width", 640))
    height = str(media.get("height", 360))
    fps = str(media.get("fps", 10))
    bitrate = str(media.get("bitrate", "512k"))
    maxrate = str(media.get("maxrate", "580k"))
    bufsize = str(media.get("bufsize", "1024k"))
    gop = str(max(1, int(float(fps))))

    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "repeat+warning",
        "-rtsp_transport", "tcp",
        "-rtsp_flags", "prefer_tcp",
        "-fflags", "+genpts+discardcorrupt",
        "-err_detect", "ignore_err",
        "-ec", "guess_mvs+deblock",
        "-use_wallclock_as_timestamps", "1",
        "-analyzeduration", "5000000",
        "-probesize", "5000000",
        "-reorder_queue_size", "1024",
        "-max_delay", "500000",
        "-i", input_url,
        "-map", "0:v:0",
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-profile:v", "main",
        "-level", "4.1",
        "-bf", "0",
        "-b:v", bitrate,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-x264-params", "repeat-headers=1:aud=1:nal-hrd=cbr",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        "-r", fps,
        "-vsync", "cfr",
        "-g", gop,
        "-keyint_min", gop,
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-pkt_size", "1200",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        publish_url,
    ]


def command_text(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)
