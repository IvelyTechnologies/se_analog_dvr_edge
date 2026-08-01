# Production Guide

Ively Analog DVR Edge is a standalone edge service for analog DVR per-channel RTSP ingestion.

## Product Features

- Runs as `analog-dvr-edge.service` under systemd.
- Starts automatically after reboot.
- Exposes local HTTP API on port `8090`.
- Supports DVR config, probe, worker reload, stop, status, diagnostics, health, and version endpoints.
- Publishes one MediaMTX RTSP path per DVR channel.
- Does not modify or replace the existing `ively-agent` service.

## Install

```bash
cd ~/Downloads/se_analog_dvr_edge
sudo bash installer/install.sh
sudo nano /opt/ively/analog-dvr-edge/configs/dvr_channels.json
sudo systemctl restart analog-dvr-edge
```

## API

```bash
curl -s http://127.0.0.1:8090/health
curl -s http://127.0.0.1:8090/version
curl -s http://127.0.0.1:8090/status
curl -s http://127.0.0.1:8090/diagnostics
curl -s -X POST http://127.0.0.1:8090/probe
curl -s -X POST http://127.0.0.1:8090/workers/reload
```

## Logs

```bash
journalctl -u analog-dvr-edge -f
sudo tail -f /opt/ively/analog-dvr-edge/logs/app.log
```

## Stream Naming

For `site_prefix=loshitha_analog_dvr`, streams are:

```text
loshitha_analog_dvr_ch1_low
loshitha_analog_dvr_ch2_low
loshitha_analog_dvr_ch3_low
```

Backend can read:

```text
rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low
```

## Verification From Backend

```bash
ffprobe -v error -rtsp_transport tcp \
"rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low" \
-show_entries stream=codec_name,width,height -of default=nw=1
```

## Operational Rule

If `/probe` fails, do not add the camera to backend yet. First enable RTSP/ONVIF on DVR or update the RTSP URL candidates.
