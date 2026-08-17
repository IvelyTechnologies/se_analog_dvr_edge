import os
import shlex


def _reorder_queue_size() -> str:
    """Keep RTSP jitter tolerance without accumulating stale live frames."""
    raw = (os.environ.get("IVELY_ANALOG_FFMPEG_REORDER_QUEUE_SIZE") or "64").strip()
    try:
        return str(min(256, max(0, int(raw))))
    except ValueError:
        return "64"


def ffmpeg_publish_command(input_url: str, publish_url: str, media: dict) -> list[str]:
    """Build an RTSP publisher command for a DVR channel."""
    video_mode = str(media.get("video_mode", "transcode")).strip().lower()
    if video_mode not in {"copy", "transcode"}:
        raise ValueError("media.video_mode must be copy or transcode")

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "repeat+warning",
        "-rtsp_transport", "tcp", "-rtsp_flags", "prefer_tcp",
        # Bound RTSP setup/read waits so a DVR or LAN outage makes FFmpeg exit
        # and ChannelWorker can retry instead of leaving a hung publisher.
        "-timeout", "10000000",
        "-fflags", "+genpts+discardcorrupt", "-err_detect", "ignore_err",
        "-ec", "guess_mvs+deblock", "-use_wallclock_as_timestamps", "1",
        "-analyzeduration", "5000000", "-probesize", "5000000",
        "-reorder_queue_size", _reorder_queue_size(), "-max_delay", "500000",
        "-i", input_url, "-map", "0:v:0", "-an",
    ]

    if video_mode == "copy":
        return command + [
            "-c:v", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", publish_url,
        ]

    width = str(media.get("width", 640))
    height = str(media.get("height", 360))
    fps = str(media.get("fps", 10))
    bitrate = str(media.get("bitrate", "512k"))
    maxrate = str(media.get("maxrate", "580k"))
    bufsize = str(media.get("bufsize", "1024k"))
    preset = str(media.get("preset", "veryfast"))
    gop = str(max(1, int(float(fps))))

    return command + [
        "-c:v", "libx264", "-preset", preset, "-tune", "zerolatency",
        "-profile:v", "main", "-level", "4.1", "-bf", "0",
        "-b:v", bitrate, "-maxrate", maxrate, "-bufsize", bufsize,
        "-x264-params", "repeat-headers=1:aud=1:nal-hrd=cbr",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        "-r", fps, "-fps_mode", "cfr", "-g", gop, "-keyint_min", gop,
        "-sc_threshold", "0", "-pix_fmt", "yuv420p", "-pkt_size", "1200",
        "-f", "rtsp", "-rtsp_transport", "tcp", publish_url,
    ]


def command_text(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)
