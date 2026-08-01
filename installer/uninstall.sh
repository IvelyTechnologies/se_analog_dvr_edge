#!/usr/bin/env bash
set -euo pipefail
SERVICE="analog-dvr-edge.service"
sudo systemctl stop "$SERVICE" || true
sudo systemctl disable "$SERVICE" || true
sudo rm -f "/etc/systemd/system/$SERVICE"
sudo systemctl daemon-reload
sudo systemctl reset-failed "$SERVICE" || true
echo "Uninstalled service. Project files remain at /opt/ively/analog-dvr-edge"
