# Analog DVR Edge Complete Setup Guide

This guide installs **SE Analog DVR Edge** on a Mini PC with the Ively Media
Base already provisioned. It reads individual analog DVR channels over local
RTSP and publishes them through MediaMTX and WireGuard. A DVR-only site does
not need the `ively-agent` NVR publisher or any NVR camera configuration.

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

- Ively Media Base provisioning (MediaMTX + WireGuard)
- MediaMTX service running
- WireGuard tunnel connected to the backend server
- Network connection to the DVR LAN

Do not install this service on a blank Mini PC until MediaMTX and WireGuard
provisioning has been completed. The installer checks for `mediamtx.service`.

For the first test, configure only Channel 1. Add remaining channels only after Channel 1 works end to end.

## 3. Configure the DVR

The menu names vary by manufacturer, but the required settings are the same:

1. Sign in to the DVR local web interface.
2. Open the camera/channel encoding or video settings page.
3. Select **Channel 1**.
4. Under **Main Stream**, set:
   - Video enabled
   - Compression: **H.264**
   - Frame rate: **10 FPS**
   - Bit rate type: **CBR**
   - I-frame interval: **1 second**
   - Bit rate: **768 Kb/s** if supported; otherwise use **512 Kb/s**
   - Resolution: keep the DVR-supported resolution
5. Enable local RTSP in the DVR network, connection, or port settings. Record
   the RTSP port and the vendor's documented per-channel stream path.
6. Save or Apply.
7. Repeat for each channel that must be used later.

Use the main stream when it is H.264 and the Mini PC has adequate bandwidth.
Use a substream when bandwidth or CPU is limited. RTSP port is commonly \`554\`,
but use the value configured on the customer DVR. ONVIF can help discovery but
is not required when direct RTSP works.

## 4. Test DVR RTSP Before Installing the Edge Service

Connect a laptop to the same local LAN/Wi-Fi as the DVR. The laptop must reach the DVR IP address.

In VLC choose **Media -> Open Network Stream** and enter the exact RTSP URL
from that DVR/NVR vendor documentation or working mobile/VMS setup:

\`\`\`text
rtsp://USERNAME:PASSWORD@DVR_IP:RTSP_PORT/VENDOR_CHANNEL_PATH
\`\`\`

If a password contains reserved URL characters such as \`@\`, encode them only
when testing a complete URL manually. In the Analog DVR Edge UI, enter the raw
password; the agent encodes it safely.

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

## 6. Configure Through the Local UI

Open this page on the Mini PC:

\`\`\`text
http://127.0.0.1:8090/setup
\`\`\`

Fill the fields in this order:

1. **Stream Prefix**: a unique site name, such as \`customer_site_dvr\`.
2. **DVR Channels**: start with \`1\`; add more only after the first works.
3. **DVR IP Address**, **Username**, and **Password**: the local DVR values.
4. **Video Mode**: choose H.264 passthrough for an H.264 input. Choose H.264
   transcode for an H.265 source or where resolution/FPS must change.
5. **RTSP URL Candidates**: enter the exact vendor URL template. Use
   \`{username}\`, \`{password}\`, \`{ip}\`, and \`{channel}\` placeholders.
   Put the most likely working URL first; the agent tries each candidate in
   order for every channel.
6. **Standalone Mobile HLS**: for this DVR-only Mini PC, select
   **Manage 30-second mobile buffer**.
7. Click **Save**, then **Test Channels**. Confirm required channels report
   \`ok: true\`.
8. Click **Apply and Start**. If the status says that MediaMTX configuration
   was updated, run the displayed manual maintenance sequence once:

   ```bash
   sudo systemctl restart mediamtx
   sleep 5
   sudo systemctl restart analog-dvr-edge
   ```

   This is required only when DVR paths or HLS settings actually changed. Normal
   saves, stream recovery, LAN recovery, and browser playback do not restart
   MediaMTX.

Customer and Site selection is optional. It appears after setting
\`IVELY_API_BASE\` and \`IVELY_API_TOKEN\` in the service environment; it uses
the cloud API only and does not store database credentials on the Mini PC.

## 7. Test and Preview Streams in the Local UI

After **Apply and Start**, the Stream Status panel shows each stream name,
publisher state, and restart count. Each running channel also shows:

- **HLS Preview**: opens the local MediaMTX HLS player on port \`8888\`.
- **WebRTC Preview**: opens the local MediaMTX WebRTC player on port \`8889\`.

Use these preview buttons to confirm real playback directly on the Mini PC. If
Test Channels fails, check the DVR IP, credentials, RTSP port, channel mapping,
camera signal, and Mini PC-to-DVR LAN connection before continuing.

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

### Mobile HLS Behavior

For a DVR-only Mini PC, enable **Standalone Mobile HLS** in the local setup UI.
Analog DVR Edge then writes the local MediaMTX configuration with two-second
segments and 45 retained segments. A one-time, manual MediaMTX restart is
required only when those settings or the DVR publisher paths change. The
dashboard player intentionally starts
around 30 seconds behind live, which prevents short mobile-data delays from
freezing the video.

For a Mini PC that already runs NVR Ively Edge, choose **Use existing MediaMTX
settings** instead. Ively Edge owns the shared MediaMTX file in that case, so a
second HLS configuration is not written by Analog DVR Edge.

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

When the Ively Edge project is upgraded at the same time, it regenerates the
shared MediaMTX configuration. Complete that upgrade first, then run:

\`\`\`bash
sudo systemctl restart ively-agent
sleep 5
sudo systemctl restart analog-dvr-edge
\`\`\`

This ensures the analog publishers reconnect to the regenerated MediaMTX paths.
