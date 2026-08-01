# SE Analog DVR Edge

Separate edge-side agent for analog DVR channel streaming.

This project is for DVRs where analog cameras are connected by BNC/coax, but the DVR exposes each channel as RTSP. It publishes each DVR channel into the same MediaMTX style used by Ively Edge, without touching the existing IP camera edge pipeline.

## Main Flow

```text
Analog Camera -> DVR Channel RTSP -> analog-dvr-edge FFmpeg worker -> MediaMTX -> Backend RTSP/HLS/WebRTC -> Dashboard
```

## What This Project Does

- Runs as a systemd service, similar to Ively Edge.
- Provides a local provisioning API on port 8090.
- Supports config, probe, start, stop, reload, and status endpoints.

- Probes DVR per-channel RTSP URLs.
- Starts one FFmpeg publisher per working channel.
- Publishes each channel into MediaMTX as browser-safe H.264.
- Keeps stream names separate from current IP camera streams.

Example stream names:

```text
loshitha_analog_dvr_ch1_low
loshitha_analog_dvr_ch2_low
loshitha_analog_dvr_ch3_low
loshitha_analog_dvr_ch4_low
```

## What This Project Does Not Do Yet

- It does not modify `se_backend`.
- It does not modify `se_dashboard` or `se_admin`.
- It does not replace `se_ively_edge`.
- It does not use HDMI crop as the main solution.

## First Test

Edit config:

```bash
cp configs/dvr_channels.sample.json configs/dvr_channels.json
nano configs/dvr_channels.json
```

Probe DVR channels:

```bash
python3 -m agent.main --config configs/dvr_channels.json --probe-only
```

Run locally:

```bash
python3 -m agent.main --config configs/dvr_channels.json
```

Check from backend server:

```bash
ffprobe -v error -rtsp_transport tcp rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low -show_entries stream=codec_name,width,height -of default=nw=1
```

## Production Install Later

Use files under `installer/` and `systemd/` on the Mini PC after DVR RTSP URLs are confirmed.

