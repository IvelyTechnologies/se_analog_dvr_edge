#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="/opt/ively/analog-dvr-edge"
SERVICE="analog-dvr-edge.service"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required" >&2
  exit 1
fi
if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffprobe is required" >&2
  exit 1
fi

sudo mkdir -p "$DEST"
if command -v rsync >/dev/null 2>&1; then
  sudo rsync -a --delete \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude '.idea/' \
    --exclude 'configs/dvr_channels.json' \
    "$SRC_DIR/" "$DEST/"
else
  # Preserve the customer DVR configuration when rsync is unavailable.
  # A plain copy can leave an obsolete source file behind, but it must never
  # delete the only copy of dvr_channels.json during an upgrade.
  sudo cp -a "$SRC_DIR/." "$DEST/"
  sudo rm -rf "$DEST/.git" "$DEST/.idea" "$DEST/venv"
  sudo find "$DEST" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  sudo find "$DEST" -type f -name '*.pyc' -delete 2>/dev/null || true
fi

sudo python3 -m venv "$DEST/venv"
sudo "$DEST/venv/bin/pip" install --upgrade pip
if [ -s "$DEST/requirements.txt" ]; then
  sudo "$DEST/venv/bin/pip" install -r "$DEST/requirements.txt"
fi
sudo chmod +x "$DEST/installer/run-analog-dvr-edge.sh" "$DEST/installer/uninstall.sh"
sudo mkdir -p "$DEST/logs"

if [ ! -f "$DEST/configs/dvr_channels.json" ]; then
  sudo cp "$DEST/configs/dvr_channels.sample.json" "$DEST/configs/dvr_channels.json"
fi

sudo cp "$DEST/systemd/$SERVICE" "/etc/systemd/system/$SERVICE"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"

echo "Installed $SERVICE to $DEST"
echo "Setup UI (open on the Mini PC): http://127.0.0.1:8090/setup"
echo "Fallback config file: sudo nano $DEST/configs/dvr_channels.json"
echo "Start: sudo systemctl restart $SERVICE"
echo "Health: curl -s http://127.0.0.1:8090/health"
echo "Probe: curl -s -X POST http://127.0.0.1:8090/probe"
