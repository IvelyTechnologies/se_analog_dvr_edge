# SE Analog DVR Edge

Production edge-side agent for analog DVR channel streaming.

This project is for customer sites where analog cameras are connected to a DVR by BNC/coax, and the DVR exposes each camera channel as RTSP/ONVIF. It publishes each DVR channel into MediaMTX using the same stream style consumed by SmartEye backend, dashboard, and admin.

For the complete vendor-neutral deployment process, see
\`docs/COMPLETE_ANALOG_DVR_SETUP.md\`.

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

For a DVR-only customer, this does **not** require an NVR camera configuration
or the `ively-agent` NVR publisher. It does require the Ively Media Base:
MediaMTX and WireGuard must be provisioned on the Mini PC first. The installer
checks for `mediamtx.service` and stops with a clear error if that prerequisite
is missing.

```bash
cd ~/Downloads/se_analog_dvr_edge
sudo bash installer/install.sh
sudo systemctl restart analog-dvr-edge
```

Open the Mini PC browser at `http://127.0.0.1:8090/setup` to configure DVR IP,
credentials, channels, RTSP candidates, and publish mode. Leaving the password
blank during an update keeps the previously saved password.

### Cloud Customer And Site Selection

The setup page uses the same authenticated cloud REST API pattern as the IP
camera Edge provisioner. It does not connect to the production database.
Configure a service token on the Mini PC before using Customer, Site, and
dashboard-camera selection:

```bash
sudo systemctl edit analog-dvr-edge
```

Add only the following, using the existing service token value:

```ini
[Service]
Environment="IVELY_API_BASE=https://api.ivelytech.com"
Environment="IVELY_API_TOKEN=REPLACE_WITH_EDGE_SERVICE_TOKEN"
```

Then apply it:

```bash
sudo systemctl daemon-reload
sudo systemctl restart analog-dvr-edge
```

The browser calls the local Mini PC service only. The local service calls the
cloud API, keeps the token private, and stores selected customer/site/camera
metadata alongside the DVR configuration. It does not alter stream names,
FFmpeg workers, or existing NVR Edge publishing.

### Recovery Behavior

- The service starts automatically after a Mini PC reboot and waits for MediaMTX.
- Analog DVR Edge never restarts a healthy MediaMTX service. It only retries its own affected DVR publishers.
- If the DVR or local LAN is unavailable during boot, it retries DVR discovery every 10 seconds.
- If an active DVR RTSP connection drops, its FFmpeg publisher exits within the timeout and retries every 5 seconds.
- The Ively Edge MediaMTX generator preserves Analog DVR publisher paths, so an NVR Edge update does not remove Analog streams.

### Mobile HLS Playback Buffer

Analog DVR Edge and Ively Edge publish into the same local MediaMTX service.
For an existing NVR + DVR installation, Ively Edge owns HLS segment retention
and Analog DVR Edge must use the existing settings.

For a DVR-only installation, the setup UI enables **Standalone Mobile HLS** by
default. This writes the following profile to the MediaMTX configuration:

```text
hlsSegmentDuration: 2s
hlsSegmentCount: 45
```

MediaMTX watches this configuration and reloads it without a process restart.
The DVR Edge starts (or retries) its publishers after a path or HLS-profile
update. Normal configuration saves, camera recovery, LAN recovery, browser
playback, and boot recovery must not restart MediaMTX.

For the mobile HLS playback profile, Ively Edge retains 45 two-second segments
(about 90 seconds). The dashboard player starts roughly 30 seconds behind the
live edge. This gives phone networks time to fetch already-created segments and
applies equally to NVR and analog DVR streams.

Restart MediaMTX only for explicit MediaMTX maintenance, an actual MediaMTX
failure, or a power-recovery issue that prevents it from becoming active. A
normal DVR Edge restart does not restart MediaMTX.

Then confirm an analog path has republished before checking the dashboard:

```bash
ffprobe -v error -rtsp_transport tcp \
  "rtsp://127.0.0.1:8554/your_site_ch1_low" \
  -show_entries stream=codec_name,width,height -of default=nw=1
curl -sSL "http://127.0.0.1:8888/your_site_ch1_low/index.m3u8" | head
```

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
