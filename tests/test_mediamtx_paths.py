from pathlib import Path

from agent.mediamtx_paths import ensure_publisher_paths


def test_existing_paths_are_not_registered_again(tmp_path: Path) -> None:
    config_path = tmp_path / "mediamtx.yml"
    config_path.write_text(
        "paths:\n\n"
        "  loshitha_mettupalayam_office_cam1_low:\n"
        "    source: publisher\n\n"
        "  loshitha_analog_dvr_ch1_low:\n"
        "    source: publisher\n"
        "  loshitha_analog_dvr_ch2_low:\n"
        "    source: publisher\n",
        encoding="utf-8",
    )

    assert ensure_publisher_paths(
        ["loshitha_analog_dvr_ch1_low", "loshitha_analog_dvr_ch2_low"], config_path
    ) == []


def test_missing_path_is_added_without_removing_existing_path(tmp_path: Path) -> None:
    config_path = tmp_path / "mediamtx.yml"
    config_path.write_text(
        "paths:\n  original_camera:\n    source: publisher\n", encoding="utf-8"
    )

    assert ensure_publisher_paths(["loshitha_analog_dvr_ch1_low"], config_path) == [
        "loshitha_analog_dvr_ch1_low"
    ]
    output = config_path.read_text(encoding="utf-8")
    assert "original_camera" in output
    assert "loshitha_analog_dvr_ch1_low" in output
