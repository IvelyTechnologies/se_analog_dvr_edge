import json
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


def test_start_does_not_block_publishers_when_paths_were_added(tmp_path, monkeypatch):
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

    status = runtime.start()

    assert status["last_start_error"] == "No DVR channel is reachable yet; retrying automatically."
    runtime.stop()


def test_standalone_hls_is_opt_in_and_restarts_mediamtx(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "mediamtx.yml"
    config_path.write_text("paths:\n", encoding="utf-8")
    runtime = AnalogDvrRuntime()
    restarted: list[list[str]] = []

    def fake_run(command, **_kwargs):
        restarted.append(command)

    monkeypatch.setattr("agent.runtime.subprocess.run", fake_run)
    config = {
        "mediamtx": {
            "manage_hls": True,
            "config_path": str(config_path),
            "hls_segment_duration": "2s",
            "hls_segment_count": 45,
        }
    }

    assert runtime._configure_standalone_mobile_hls(config) is True
    assert restarted == [["systemctl", "restart", "mediamtx"]]
    assert runtime._configure_standalone_mobile_hls(config) is False
    assert restarted == [["systemctl", "restart", "mediamtx"]]


def test_shared_mediamtx_hls_is_not_changed_without_opt_in(tmp_path: Path) -> None:
    config_path = tmp_path / "mediamtx.yml"
    original = "hlsSegmentCount: 15\npaths:\n"
    config_path.write_text(original, encoding="utf-8")
    runtime = AnalogDvrRuntime()

    assert runtime._configure_standalone_mobile_hls({"mediamtx": {"config_path": str(config_path)}}) is False
    assert config_path.read_text(encoding="utf-8") == original
