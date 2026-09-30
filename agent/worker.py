import subprocess
import threading
import time
from typing import Any

from agent.logging_config import logger
from agent.publisher import command_text, ffmpeg_publish_command


class ChannelWorker:
    STALLED_PROGRESS_SECONDS = 35

    def __init__(self, name: str, input_url: str, publish_url: str, media: dict):
        self.name = name
        self.input_url = input_url
        self.publish_url = publish_url
        self.media = media
        self.stop_requested = False
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"worker:{name}")
        self.proc: subprocess.Popen | None = None
        self.restart_count = 0
        self.last_exit_code: int | None = None
        self.last_started_at: float | None = None
        self.last_stopped_at: float | None = None
        self.last_progress_at: float | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_requested = True
        proc = self.proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()

    def status(self) -> dict[str, Any]:
        proc = self.proc
        return {
            "stream_name": self.name,
            "input_url": self.input_url,
            "publish_url": self.publish_url,
            "thread_alive": self.thread.is_alive(),
            "pid": proc.pid if proc and proc.poll() is None else None,
            "process_running": bool(proc and proc.poll() is None),
            "restart_count": self.restart_count,
            "last_exit_code": self.last_exit_code,
            "last_started_at": self.last_started_at,
            "last_stopped_at": self.last_stopped_at,
            "last_progress_at": self.last_progress_at,
            "last_error": self.last_error,
        }

    def _read_ffmpeg_output(self, proc: subprocess.Popen) -> None:
        """Track FFmpeg progress while preserving warnings in the journal."""
        if proc.stderr is None:
            return
        for line in proc.stderr:
            message = line.strip()
            if "=" in message:
                key, _value = message.split("=", 1)
                if key in {
                    "bitrate", "total_size", "out_time_us", "out_time_ms",
                    "out_time", "dup_frames", "drop_frames", "speed", "progress",
                }:
                    if key == "progress":
                        self.last_progress_at = time.time()
                    continue
            if message:
                logger.warning("[%s] ffmpeg: %s", self.name, message)

    def _run(self) -> None:
        while not self.stop_requested:
            self.restart_count += 1
            cmd = ffmpeg_publish_command(self.input_url, self.publish_url, self.media)
            self.last_started_at = time.time()
            self.last_progress_at = self.last_started_at
            self.last_error = None
            logger.info("[%s] starting ffmpeg restart_count=%s", self.name, self.restart_count)
            logger.info("[%s] %s", self.name, command_text(cmd))
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                output_reader = threading.Thread(
                    target=self._read_ffmpeg_output,
                    args=(self.proc,),
                    daemon=True,
                    name=f"ffmpeg-output:{self.name}",
                )
                output_reader.start()
                while self.proc.poll() is None and not self.stop_requested:
                    time.sleep(2)
                    if time.time() - self.last_progress_at > self.STALLED_PROGRESS_SECONDS:
                        self.last_error = (
                            f"ffmpeg made no progress for {self.STALLED_PROGRESS_SECONDS} seconds"
                        )
                        logger.warning("[%s] %s; reconnecting", self.name, self.last_error)
                        self.proc.terminate()
                self.last_exit_code = self.proc.returncode
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("[%s] ffmpeg start failed", self.name)
            finally:
                self.last_stopped_at = time.time()

            if not self.stop_requested:
                logger.warning("[%s] ffmpeg exited code=%s; restarting in 5s", self.name, self.last_exit_code)
                time.sleep(5)
