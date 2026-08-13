# SE Analog DVR Edge

Production edge-side agent for analog DVR channel streaming.

This project is for customer sites where analog cameras are connected to a DVR by BNC/coax, and the DVR exposes each camera channel as RTSP/ONVIF. It publishes each DVR channel into MediaMTX using the same stream style consumed by SmartEye backend, dashboard, and admin.

## Main Flow

```text
Analog Camera -> DVR Channel RTSP -> analog-dvr-edge FFmpeg worker -> MediaMTX -> Backend RTSP/HLS/WebRTC -> Dashboard
```

## Product Features

- Runs as `analog-dvr-edge.service` under systemd.
- Starts automatically after reboot.
- Provides a local setup screen and HTTP API on port `8090`.
- Supports health, version, diagnostics, config, probe, reload, stop, and status endpoints.
- Probes DVR per-channel RTSP URLs.
- Starts one FFmpeg publisher per working DVR channel.
- Publishes each channel into MediaMTX as browser-safe H.264.
- Keeps analog DVR streams separate from existing IP camera edge streams.
- Does not modify `se_backend`, `se_dashboard`, `se_admin`, or `se_ively_edge`.

## Video Modes

Use `"video_mode": "copy"` when the DVR stream is already H.264. It republishes the original stream without CPU-heavy encoding and is recommended for multiple DVR channels.

Use `"video_mode": "transcode"` only for H.265 input or when resizing, FPS conversion, or bitrate reduction is required. In transcode mode, optional `"preset": "ultrafast"` reduces CPU use.

## Stream Names

Example for `site_prefix=loshitha_analog_dvr`:

```text
loshitha_analog_dvr_ch1_low
loshitha_analog_dvr_ch2_low
loshitha_analog_dvr_ch3_low
loshitha_analog_dvr_ch4_low
```

Backend can consume:

```text
rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low
https://api.ivelytech.com/edge-stream/10.20.0.2/loshitha_analog_dvr_ch1_low/index.m3u8
https://api.ivelytech.com/edge-webrtc/10.20.0.2/loshitha_analog_dvr_ch1_low/whep
```

## Install On Mini PC

```bash
cd ~/Downloads/se_analog_dvr_edge
sudo bash installer/install.sh
sudo systemctl restart analog-dvr-edge
```

Open the Mini PC browser at `http://127.0.0.1:8090/setup` to configure DVR IP,
credentials, channels, RTSP candidates, and publish mode. Leaving the password
blank during an update keeps the previously saved password.

## Verify Service

```bash
curl -s http://127.0.0.1:8090/health
curl -s http://127.0.0.1:8090/diagnostics
curl -s -X POST http://127.0.0.1:8090/probe
curl -s -X POST http://127.0.0.1:8090/workers/reload
curl -s http://127.0.0.1:8090/status
```

## Verify Stream On Mini PC

```bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://127.0.0.1:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
```

## Verify Stream From Backend Server

```bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
```

## Requirement

The DVR must expose per-channel RTSP/ONVIF locally. If the DVR only supports vendor cloud/P2P mobile app viewing and does not expose local RTSP/ONVIF, SmartEye cannot reliably consume individual analog channels from that DVR.
