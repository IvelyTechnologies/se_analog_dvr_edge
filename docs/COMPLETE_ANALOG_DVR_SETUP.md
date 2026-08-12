# Analog DVR Edge Complete Setup Guide

This guide installs **SE Analog DVR Edge** alongside the existing Ively Edge installation on a Mini PC. It reads individual analog DVR channels over local RTSP and publishes them through the existing MediaMTX and WireGuard pipeline.

## 1. Intended Flow

\`\`\`text
Analog camera -> DVR channel -> DVR RTSP main stream -> Analog DVR Edge
-> MediaMTX -> WireGuard -> SmartEye backend -> HLS / WebRTC -> Dashboard
\`\`\`

One configured DVR channel produces three usable outputs:

- RTSP for backend AI detection
- HLS for browser fallback playback
- WebRTC/WHEP for low-latency browser playback

This project does not replace the existing \`ively-agent\`. It publishes new, separate stream names.

## 2. Before Starting

The Mini PC must already have these working:

- Existing Ively Edge installation
- MediaMTX service running
- WireGuard tunnel connected to the backend server
- Network connection to the DVR LAN

Do not install this service on a blank Mini PC until Ively Edge / MediaMTX / WireGuard provisioning has been completed.

For the first test, configure only Channel 1. Add remaining channels only after Channel 1 works end to end.

## 3. Configure the DVR

For the Dahua/CP Plus DVR shown in the test:

1. Sign in to the DVR local web interface.
2. Open **Camera -> Encode -> Audio/Video**.
3. Select **Channel 1**.
4. Under **Main Stream**, set:
   - Video enabled
   - Compression: **H.264**
   - Frame rate: **10 FPS**
   - Bit rate type: **CBR**
   - I-frame interval: **1 second**
   - Bit rate: **768 Kb/s** if supported; otherwise use **512 Kb/s**
   - Resolution: keep the DVR-supported resolution
5. Save or Apply.
6. Repeat for each channel that must be used later.

The guide deliberately uses the Main Stream only:

\`\`\`text
subtype=0 = main stream
subtype=1 = sub stream
\`\`\`

RTSP must be enabled in DVR Network / Connection / Port settings. The usual Dahua RTSP port is \`554\`. ONVIF is useful for discovery but is not required when direct RTSP works.

## 4. Test DVR RTSP Before Installing the Edge Service

Connect a laptop to the same local LAN/Wi-Fi as the DVR. The laptop must reach the DVR IP address.

For the current DVR example:

\`\`\`text
DVR IP: 192.168.1.108
Channel: 1
RTSP port: 554
\`\`\`

In VLC choose **Media -> Open Network Stream** and enter:

\`\`\`text
rtsp://admin:YOUR_PASSWORD@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0
\`\`\`

If the password contains \`@\`, use \`%40\` only when entering a complete URL manually. Example:

\`\`\`text
rtsp://admin:loshi%402411@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0
\`\`\`

Expected result: Channel 1 video plays in VLC.

Do not install or configure the edge publisher until this test succeeds. If VLC cannot play it, fix DVR RTSP/network/credentials first.

## 5. Copy the Project to the Mini PC

Manually download/copy the project folder to the Mini PC, for example:

\`\`\`bash
cd ~/Downloads/se_analog_dvr_edge
\`\`\`

Then run:

\`\`\`bash
sudo bash installer/install.sh
\`\`\`

The installer:

- Copies the application to \`/opt/ively/analog-dvr-edge\`
- Creates a Python virtual environment
- Preserves an existing \`configs/dvr_channels.json\` during future upgrades
- Installs and enables \`analog-dvr-edge.service\`
- Does not modify \`ively-agent.service\`

## 6. Configure Channel 1

Open the deployed configuration:

\`\`\`bash
sudo nano /opt/ively/analog-dvr-edge/configs/dvr_channels.json
\`\`\`

For the first main-stream test, use this format. Put the **raw password** in JSON; do not replace \`@\` with \`%40\` here because the agent encodes it safely.

\`\`\`json
{
  "site_prefix": "loshitha_analog_dvr",
  "dvr": {
    "ip": "192.168.1.108",
    "username": "admin",
    "password": "YOUR_DVR_PASSWORD",
    "channels": [1]
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
    "rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel={channel}&subtype=0"
  ]
}
\`\`\`

The published stream name for the above configuration is:

\`\`\`text
loshitha_analog_dvr_ch1_low
\`\`\`

## 7. Probe Before Starting Workers

Run this on the Mini PC:

\`\`\`bash
cd /opt/ively/analog-dvr-edge
sudo ./venv/bin/python -m agent.main --config configs/dvr_channels.json --probe-only
\`\`\`

Expected result:

\`\`\`text
OK   rtsp://...
\`\`\`

If it shows \`FAIL\` or \`No working RTSP URL\`, stop here. Check the DVR IP, password, RTSP port, same-LAN connection, and whether Channel 1 has a camera signal.

## 8. Start the Analog DVR Edge Service

Only after the probe succeeds:

\`\`\`bash
sudo systemctl daemon-reload
sudo systemctl restart analog-dvr-edge
sudo systemctl status analog-dvr-edge --no-pager
\`\`\`

Check logs:

\`\`\`bash
journalctl -u analog-dvr-edge -f
\`\`\`

Expected log behavior: one FFmpeg publisher starts for \`loshitha_analog_dvr_ch1_low\`.

The local management API is intentionally local-only:

\`\`\`bash
curl -s http://127.0.0.1:8090/health
curl -s http://127.0.0.1:8090/status
curl -s -X POST http://127.0.0.1:8090/probe
\`\`\`

## 9. Verify Local RTSP on the Mini PC

\`\`\`bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://127.0.0.1:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
\`\`\`

Expected output includes:

\`\`\`text
codec_name=h264
width=640
height=360
\`\`\`

This confirms:

\`\`\`text
DVR RTSP -> Analog DVR Edge -> local MediaMTX
\`\`\`

## 10. Verify From the Backend Server

Replace \`EDGE_TUNNEL_IP\` with the WireGuard IP of this Mini PC.

\`\`\`bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://EDGE_TUNNEL_IP:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
\`\`\`

Then verify HLS:

\`\`\`bash
curl -s "https://api.ivelytech.com/edge-stream/EDGE_TUNNEL_IP/loshitha_analog_dvr_ch1_low/main_stream.m3u8"
\`\`\`

The response must contain \`#EXTM3U\` and \`.ts\` segments.

WebRTC endpoint:

\`\`\`text
https://api.ivelytech.com/edge-webrtc/EDGE_TUNNEL_IP/loshitha_analog_dvr_ch1_low/whep
\`\`\`

## 11. Add the Camera in SmartEye

After backend RTSP verification succeeds, add a new camera record using:

\`\`\`text
Camera source URL:
rtsp://EDGE_TUNNEL_IP:8554/loshitha_analog_dvr_ch1_low
\`\`\`

Use a separate camera name, site, and detector configuration. Do not replace an existing IP-camera stream URL.

The dashboard/live view will use the same published stream name:

\`\`\`text
RTSP:
rtsp://EDGE_TUNNEL_IP:8554/loshitha_analog_dvr_ch1_low

HLS:
https://api.ivelytech.com/edge-stream/EDGE_TUNNEL_IP/loshitha_analog_dvr_ch1_low/index.m3u8

WebRTC:
https://api.ivelytech.com/edge-webrtc/EDGE_TUNNEL_IP/loshitha_analog_dvr_ch1_low/whep
\`\`\`

Open **All Cameras View**, select the newly created analog DVR camera, and confirm WebRTC playback. If WebRTC cannot establish, the normal dashboard HLS fallback should play.

## 12. Add More Channels

After Channel 1 works, edit:

\`\`\`bash
sudo nano /opt/ively/analog-dvr-edge/configs/dvr_channels.json
\`\`\`

Change:

\`\`\`json
"channels": [1]
\`\`\`

to:

\`\`\`json
"channels": [1, 2, 3, 4]
\`\`\`

Then reload:

\`\`\`bash
sudo systemctl restart analog-dvr-edge
curl -s http://127.0.0.1:8090/status
\`\`\`

Each channel creates one independent path:

\`\`\`text
loshitha_analog_dvr_ch1_low
loshitha_analog_dvr_ch2_low
loshitha_analog_dvr_ch3_low
loshitha_analog_dvr_ch4_low
\`\`\`

Add each verified path as a separate SmartEye camera.

## 13. Failure Checklist

| Symptom | Check |
|---|---|
| VLC cannot play DVR RTSP | DVR LAN, RTSP port 554, credentials, Channel signal, RTSP enabled |
| Probe fails | Use the exact DVR IP and raw password in JSON; keep only the correct main-stream candidate |
| Service does not start | \`systemctl status analog-dvr-edge --no-pager\` and \`systemctl status mediamtx --no-pager\` |
| Local RTSP fails | \`journalctl -u analog-dvr-edge -n 100 --no-pager\` |
| Backend cannot read | WireGuard tunnel IP/routing, then test \`nc -vz EDGE_TUNNEL_IP 8554\` |
| Dashboard does not play | Confirm backend RTSP first, then check HLS and WHEP endpoint URLs |

## 14. Safe Upgrade

To update the project later:

\`\`\`bash
cd ~/Downloads/se_analog_dvr_edge
sudo bash installer/install.sh
sudo systemctl restart analog-dvr-edge
\`\`\`

The installer now preserves the live \`dvr_channels.json\` configuration.
