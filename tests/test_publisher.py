from agent.publisher import ffmpeg_publish_command


def test_publisher_command_has_rtsp_timeout_for_network_recovery():
    command = ffmpeg_publish_command(
        "rtsp://dvr.example/ch1",
        "rtsp://127.0.0.1:8554/site_analog_dvr_ch1_low",
        {"video_mode": "copy"},
    )

    assert command[command.index("-timeout") + 1] == "10000000"
    assert command[-7:] == [
        "-c:v", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", "rtsp://127.0.0.1:8554/site_analog_dvr_ch1_low",
    ]
