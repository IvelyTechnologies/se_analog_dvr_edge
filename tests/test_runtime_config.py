import json

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
