import json
import threading
import time
from pathlib import Path

from agent.runtime import AnalogDvrRuntime


def test_save_config_keeps_saved_password_when_blank(tmp_path):
    path = tmp_path / "dvr_channels.json"
    path.write_text(
        json.dumps({
            "site_prefix": "site_dvr",
            "dvr": {"ip": "192.168.1.10", "username": "admin", "password": "secret", "channels": [1]},
            "media": {"video_mode": "copy"},
            "rtsp_candidates": ["rtsp://{ip}/{channel}"],
        }),
        encoding="utf-8",
    )
    runtime = AnalogDvrRuntime(str(path))
    config = runtime.public_config()
    config["dvr"]["password"] = ""
    runtime.save_config(config)
    assert runtime.load()["dvr"]["password"] == "secret"


def test_start_schedules_recovery_when_all_dvr_channels_are_unreachable(tmp_path, monkeypatch):
    path = tmp_path / "dvr_channels.json"
    path.write_text(
        json.dumps({
            "site_prefix": "site_dvr",
            "dvr": {"ip": "192.168.1.10", "channels": [1]},
            "media": {"video_mode": "copy"},
            "rtsp_candidates": ["rtsp://{ip}/{channel}"],
        }),
        encoding="utf-8",
    )
    runtime = AnalogDvrRuntime(str(path))
    monkeypatch.setattr(runtime, "_ensure_mediamtx_paths", lambda _config: [])
    monkeypatch.setattr(runtime, "probe", lambda: [])

    status = runtime.start()

    assert status["running"] is False
    assert status["last_start_error"] == "No DVR channel is reachable yet; retrying automatically."
    assert runtime._recovery_thread is not None
    runtime.stop()


def test_start_continues_when_paths_are_added_by_mediamtx_hot_reload(tmp_path, monkeypatch):
    path = tmp_path / "dvr_channels.json"
    path.write_text(
        json.dumps({
            "site_prefix": "site_dvr",
            "dvr": {"ip": "192.168.1.10", "channels": [1]},
            "media": {"video_mode": "copy"},
            "rtsp_candidates": ["rtsp://{ip}/{channel}"],
        }),
        encoding="utf-8",
    )
    runtime = AnalogDvrRuntime(str(path))
    monkeypatch.setattr(runtime, "_ensure_mediamtx_paths", lambda _config: ["site_dvr_ch1_low"])
    monkeypatch.setattr(runtime, "probe", lambda: [])
    monkeypatch.setattr(runtime, "_schedule_recovery_locked", lambda: None)

    status = runtime.start()

    assert status["running"] is False
    assert status["last_start_error"] == "No DVR channel is reachable yet; retrying automatically."
    runtime.stop()


def test_partial_start_schedules_recovery_for_only_unreachable_channels(tmp_path, monkeypatch):
    path = tmp_path / "dvr_channels.json"
    path.write_text(
        json.dumps({
            "site_prefix": "site_dvr",
            "dvr": {"ip": "192.168.1.10", "channels": [1, 2]},
            "media": {"video_mode": "copy"},
            "rtsp_candidates": ["rtsp://{ip}/{channel}"],
        }),
        encoding="utf-8",
    )
    runtime = AnalogDvrRuntime(str(path))
    monkeypatch.setattr(runtime, "_ensure_mediamtx_paths", lambda _config: [])
    monkeypatch.setattr(runtime, "_schedule_recovery_locked", lambda: None)
    monkeypatch.setattr(
        runtime,
        "probe",
        lambda _channels=None: [
            {"channel": 1, "stream_name": "site_dvr_ch1_low", "ok": False, "selected_url": None, "attempts": []},
            {"channel": 2, "stream_name": "site_dvr_ch2_low", "ok": True, "selected_url": "rtsp://192.168.1.10/2", "attempts": []},
        ],
    )

    class Worker:
        def __init__(self, *args):
            self.name = args[0]

        def start(self):
            pass

        def stop(self):
            pass

        def status(self):
            return {"stream_name": self.name, "input_url": "", "publish_url": "", "thread_alive": True, "process_running": True}

    monkeypatch.setattr("agent.runtime.ChannelWorker", Worker)

    status = runtime.start()

    assert status["running"] is True
    assert status["last_start_error"] == "DVR channels 1 are unavailable; retrying automatically."
    assert [worker.name for worker in runtime.workers] == ["site_dvr_ch2_low"]
    runtime.stop()


def test_status_is_available_while_a_slow_dvr_probe_runs(tmp_path, monkeypatch):
    path = tmp_path / "dvr_channels.json"
    path.write_text(
        json.dumps({
            "site_prefix": "site_dvr",
            "dvr": {"ip": "192.168.1.10", "channels": [1]},
            "media": {"video_mode": "copy"},
            "rtsp_candidates": ["rtsp://{ip}/{channel}"],
        }),
        encoding="utf-8",
    )
    runtime = AnalogDvrRuntime(str(path))
    probe_started = threading.Event()
    release_probe = threading.Event()

    monkeypatch.setattr(runtime, "_ensure_mediamtx_paths", lambda _config: [])

    def slow_probe():
        probe_started.set()
        release_probe.wait(timeout=2)
        return []

    monkeypatch.setattr(runtime, "probe", slow_probe)
    thread = threading.Thread(target=runtime.start)
    thread.start()
    assert probe_started.wait(timeout=1)

    started = time.monotonic()
    runtime.status()
    assert time.monotonic() - started < 0.2

    release_probe.set()
    thread.join(timeout=2)
    runtime.stop()


def test_standalone_hls_is_opt_in_without_restarting_mediamtx(tmp_path: Path) -> None:
    config_path = tmp_path / "mediamtx.yml"
    config_path.write_text("paths:\n", encoding="utf-8")
    runtime = AnalogDvrRuntime()
    config = {
        "mediamtx": {
            "manage_hls": True,
            "config_path": str(config_path),
            "hls_segment_duration": "2s",
            "hls_segment_count": 45,
        }
    }

    assert runtime._configure_standalone_mobile_hls(config) is True
    assert runtime._configure_standalone_mobile_hls(config) is False


def test_shared_mediamtx_hls_is_not_changed_without_opt_in(tmp_path: Path) -> None:
    config_path = tmp_path / "mediamtx.yml"
    original = "hlsSegmentCount: 15\npaths:\n"
    config_path.write_text(original, encoding="utf-8")
    runtime = AnalogDvrRuntime()

    assert runtime._configure_standalone_mobile_hls({"mediamtx": {"config_path": str(config_path)}}) is False
    assert config_path.read_text(encoding="utf-8") == original


def test_standalone_start_does_not_block_on_mediamtx_hot_reload(tmp_path: Path, monkeypatch) -> None:
    media_config = tmp_path / "mediamtx.yml"
    media_config.write_text("paths:\n", encoding="utf-8")
    config_path = tmp_path / "dvr_channels.json"
    config_path.write_text(
        json.dumps(
            {
                "site_prefix": "hikvision_analog_dvr",
                "dvr": {"ip": "192.168.1.64", "channels": [1]},
                "media": {"video_mode": "copy"},
                "mediamtx": {
                    "manage_hls": True,
                    "config_path": str(media_config),
                    "hls_segment_duration": "2s",
                    "hls_segment_count": 45,
                },
                "rtsp_candidates": ["rtsp://{ip}/Streaming/Channels/{channel}01"],
            }
        ),
        encoding="utf-8",
    )
    runtime = AnalogDvrRuntime(str(config_path))
    monkeypatch.setattr(runtime, "probe", lambda: [])
    monkeypatch.setattr(runtime, "_schedule_recovery_locked", lambda: None)

    status = runtime.start()

    updated = media_config.read_text()
    assert "hlsSegmentDuration: 2s" in updated
    assert "hlsSegmentCount: 45" in updated
    assert "hikvision_analog_dvr_ch1_low:" in updated
    assert status["running"] is False
    assert status["last_start_error"] == "No DVR channel is reachable yet; retrying automatically."
    runtime.stop()
