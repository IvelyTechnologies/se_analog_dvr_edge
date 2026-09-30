from agent.dvr_rtsp import format_rtsp_url


def test_rtsp_url_template_encodes_credentials_and_formats_channel() -> None:
    dvr = {
        "ip": "192.168.1.64",
        "username": "admin",
        "password": "P@ss word",
    }

    url = format_rtsp_url(
        "rtsp://{username}:{password}@{ip}:554/custom/channel/{channel}01",
        dvr,
        2,
    )

    assert url == "rtsp://admin:P%40ss%20word@192.168.1.64:554/custom/channel/201"
