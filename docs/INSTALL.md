# Install And Test

On Mini PC:

```bash
cd ~/Downloads/se_analog_dvr_edge
sudo bash installer/install.sh
sudo nano /opt/ively/analog-dvr-edge/configs/dvr_channels.json
```

Probe first:

```bash
cd /opt/ively/analog-dvr-edge
sudo ./venv/bin/python -m agent.main --config configs/dvr_channels.json --probe-only
```

If channels are OK, install service:

```bash
sudo cp /opt/ively/analog-dvr-edge/systemd/analog-dvr-edge.service /etc/systemd/system/analog-dvr-edge.service
sudo systemctl daemon-reload
sudo systemctl enable analog-dvr-edge
sudo systemctl restart analog-dvr-edge
sudo systemctl status analog-dvr-edge --no-pager
```

Check logs:

```bash
journalctl -u analog-dvr-edge -f
```

Check local MediaMTX stream on Mini PC:

```bash
ffprobe -v error -rtsp_transport tcp rtsp://127.0.0.1:8554/loshitha_analog_dvr_ch1_low -show_entries stream=codec_name,width,height -of default=nw=1
```

Check from backend server over WireGuard:

```bash
ffprobe -v error -rtsp_transport tcp rtsp://10.20.0.2:8554/loshitha_analog_dvr_ch1_low -show_entries stream=codec_name,width,height -of default=nw=1
```
