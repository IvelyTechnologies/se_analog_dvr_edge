# DVR RTSP Notes

Try the DVR vendor mobile app information first. The app usually works because the DVR has one of these:

1. Local RTSP/ONVIF stream per channel.
2. Vendor cloud/P2P relay.

For SmartEye, local RTSP/ONVIF is best.

Common URL patterns:

```text
Dahua / CP Plus:
rtsp://USER:PASS@DVR_IP:554/cam/realmonitor?channel=1&subtype=0
rtsp://USER:PASS@DVR_IP:554/cam/realmonitor?channel=1&subtype=1

Hikvision / Prama:
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/101
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/102
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/201
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/202
```

If RTSP does not work:

- Enable RTSP in DVR network settings.
- Enable ONVIF if available.
- Check DVR port 554.
- Try substream first for stability.
- Confirm username/password works from LAN.
