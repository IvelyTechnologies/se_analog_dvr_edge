# Analog DVR Edge Complete Setup Guide

This guide is for installing analog DVR camera streaming without changing the existing Ively IP camera edge pipeline.

The DVR brand/model can change per customer. The common setup remains the same:

```text
Analog Cameras -> DVR -> Per-channel RTSP/ONVIF -> Analog DVR Edge -> MediaMTX -> Backend -> Dashboard
```

## 1. What Must Be Possible

The DVR must expose each analog channel as a network stream.

Good:

```text
DVR Channel 1 -> RTSP URL
DVR Channel 2 -> RTSP URL
DVR Channel 3 -> RTSP URL
```

Not enough:

```text
Only HDMI grid output
Only vendor mobile app without local RTSP/ONVIF
Only web page view without stream URL
```

If DVR mobile app works, it does not always mean local RTSP is enabled. Vendor apps may use cloud/P2P. For SmartEye, we need local RTSP/ONVIF or a documented DVR stream URL.

## 2. Site Information To Collect

For each customer site, collect:

```text
DVR brand:
DVR model:
DVR local IP:
DVR username:
DVR password:
Number of channels:
RTSP enabled: yes/no
ONVIF enabled: yes/no
RTSP port: usually 554
DVR mobile app name:
```

Even if brand/model changes, these fields are enough to test.

## 3. DVR Settings To Enable

On DVR local menu or web UI:

1. Set static LAN IP for DVR.
2. Enable RTSP.
3. Enable ONVIF if available.
4. Create/confirm user account with live view permission.
5. Confirm RTSP port, usually `554`.
6. Enable substream for each channel if available.
7. Set substream codec to H.264 if option exists.
8. Set substream resolution/FPS reasonably:
   - 640x360 or 704x576
   - 8-12 FPS
   - 300k-800k bitrate

Why substream first?

Substream is usually more stable and lighter. Main stream can be tested later if HD is required.

## 4. Common DVR RTSP URL Patterns

### Dahua / CP Plus

```text
rtsp://USER:PASS@DVR_IP:554/cam/realmonitor?channel=1&subtype=0
rtsp://USER:PASS@DVR_IP:554/cam/realmonitor?channel=1&subtype=1
```

- `subtype=0` = main stream
- `subtype=1` = substream

### Hikvision / Prama

```text
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/101
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/102
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/201
rtsp://USER:PASS@DVR_IP:554/Streaming/Channels/202
```

- `101` = channel 1 main
- `102` = channel 1 sub
- `201` = channel 2 main
- `202` = channel 2 sub

### Generic Older DVRs

```text
rtsp://USER:PASS@DVR_IP:554/ch01/0
rtsp://USER:PASS@DVR_IP:554/ch01/1
rtsp://USER:PASS@DVR_IP:554/user=USER_password=PASS_channel=1_stream=0.sdp
rtsp://USER:PASS@DVR_IP:554/user=USER_password=PASS_channel=1_stream=1.sdp
```

## 5. Install Project On Mini PC

Copy this project to Mini PC, then run:

```bash
cd ~/Downloads/se_analog_dvr_edge
sudo bash installer/install.sh
```

This installs to:

```text
/opt/ively/analog-dvr-edge
```

## 6. Configure DVR Channels

Create config:

```bash
cd /opt/ively/analog-dvr-edge
sudo cp configs/dvr_channels.sample.json configs/dvr_channels.json
sudo nano configs/dvr_channels.json
```

Example:

```json
{
  "site_prefix": "loshitha_analog_dvr",
  "dvr": {
    "ip": "192.168.1.10",
    "username": "admin",
    "password": "password",
    "channels": [1, 2, 3, 4]
  },
  "media": {
    "rtsp_publish_host": "127.0.0.1",
    "rtsp_publish_port": 8554,
    "width": 640,
    "height": 360,
    "fps": 10,
    "bitrate": "512k",
    "maxrate": "580k",
    "bufsize": "1024k"
  },
  "rtsp_candidates": [
    "rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel={channel}&subtype=1",
    "rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel={channel}&subtype=0",
    "rtsp://{username}:{password}@{ip}:554/Streaming/Channels/{channel}02",
    "rtsp://{username}:{password}@{ip}:554/Streaming/Channels/{channel}01"
  ]
}
```

## 7. Probe RTSP Before Publishing

Run:

```bash
cd /opt/ively/analog-dvr-edge
sudo ./venv/bin/python -m agent.main --config configs/dvr_channels.json --probe-only
```

Expected:

```text
=== channel=1 stream=loshitha_analog_dvr_ch1_low ===
OK rtsp://...
codec_name=h264
width=640
height=360
```

If all URLs fail:

1. DVR RTSP may be disabled.
2. Username/password may be wrong.
3. DVR port 554 may be blocked.
4. URL pattern may be different for that brand.
5. DVR may only support vendor cloud/P2P, not local RTSP.

## 8. Start Publishing Streams

If probe works:

```bash
sudo cp /opt/ively/analog-dvr-edge/systemd/analog-dvr-edge.service /etc/systemd/system/analog-dvr-edge.service
sudo systemctl daemon-reload
sudo systemctl enable analog-dvr-edge
sudo systemctl restart analog-dvr-edge
sudo systemctl status analog-dvr-edge --no-pager
```

Watch logs:

```bash
journalctl -u analog-dvr-edge -f
```

## 9. Verify On Mini PC

```bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://127.0.0.1:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
```

Expected:

```text
codec_name=h264
width=640
height=360
```

## 10. Verify From Backend Server

From backend server:

```bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
```

If this works, backend can read the analog DVR stream.

## 11. Backend/Dashboard Integration

Only after stream is stable, add camera records using stream names:

```text
loshitha_analog_dvr_ch1_low
loshitha_analog_dvr_ch2_low
loshitha_analog_dvr_ch3_low
loshitha_analog_dvr_ch4_low
```

Backend RTSP:

```text
rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low
```

Backend HLS:

```text
https://api.ivelytech.com/edge-stream/10.20.0.2/loshitha_analog_dvr_ch1_low/index.m3u8
```

Backend WebRTC:

```text
https://api.ivelytech.com/edge-webrtc/10.20.0.2/loshitha_analog_dvr_ch1_low/whep
```

## 12. Stability Test

Run from backend server for 30-60 minutes:

```bash
while true; do
  date '+%H:%M:%S'
  timeout 8 ffprobe -v error -rtsp_transport tcp \
  "rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low" \
  -show_entries stream=codec_name,width,height -of default=nw=1
  echo "EXIT=$?"
  sleep 10
done
```

Good output:

```text
EXIT=0
EXIT=0
EXIT=0
```

Bad output:

```text
DESCRIBE failed: 404
Connection refused
EXIT=124
```

If bad output appears, issue is usually DVR RTSP instability, Mini PC network, or MediaMTX publisher restart.

## 13. Rollback

Stop analog DVR edge service:

```bash
sudo systemctl stop analog-dvr-edge
sudo systemctl disable analog-dvr-edge
```

This does not affect existing `ively-agent` IP camera pipeline.

## 14. Final Recommendation

Use this order for every customer:

1. Confirm DVR network IP.
2. Enable RTSP/ONVIF.
3. Probe per-channel RTSP.
4. Publish test stream through analog DVR edge.
5. Verify from backend server.
6. Add to dashboard/backend only after stable test.

Do not use HDMI crop unless DVR has no per-channel RTSP and the customer accepts lower quality and fixed grid limitations.
