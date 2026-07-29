import subprocess
import threading
import time

from agent.publisher import command_text, ffmpeg_publish_command


class ChannelWorker:
    def __init__(self, name: str, input_url: str, publish_url: str, media: dict):
        self.name = name
        self.input_url = input_url
        self.publish_url = publish_url
        self.media = media
        self.stop_requested = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_requested = True

    def _run(self) -> None:
        attempt = 0
        while not self.stop_requested:
            attempt += 1
            cmd = ffmpeg_publish_command(self.input_url, self.publish_url, self.media)
            print(f"[{self.name}] starting ffmpeg attempt={attempt}")
            print(f"[{self.name}] {command_text(cmd)}")
            proc = subprocess.Popen(cmd)
            while proc.poll() is None and not self.stop_requested:
                time.sleep(2)
            if self.stop_requested and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
            code = proc.returncode
            if not self.stop_requested:
                print(f"[{self.name}] ffmpeg exited code={code}; restarting in 5s")
                time.sleep(5)
