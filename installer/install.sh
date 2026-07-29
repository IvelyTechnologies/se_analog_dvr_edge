#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="/opt/ively/analog-dvr-edge"

sudo mkdir -p "$DEST"
sudo rsync -a --delete "$SRC_DIR/" "$DEST/"
sudo python3 -m venv "$DEST/venv"
sudo "$DEST/venv/bin/pip" install --upgrade pip
sudo "$DEST/venv/bin/pip" install -r "$DEST/requirements.txt"
sudo chmod +x "$DEST/installer/run-analog-dvr-edge.sh"

if [ ! -f "$DEST/configs/dvr_channels.json" ]; then
  sudo cp "$DEST/configs/dvr_channels.sample.json" "$DEST/configs/dvr_channels.json"
fi

echo "Installed to $DEST"
echo "Edit: sudo nano $DEST/configs/dvr_channels.json"
echo "Probe: cd $DEST && sudo ./venv/bin/python -m agent.main --config configs/dvr_channels.json --probe-only"
