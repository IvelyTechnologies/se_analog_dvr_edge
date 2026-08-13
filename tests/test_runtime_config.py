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
