#!/usr/bin/env bash
set -euo pipefail
cd /opt/ively/analog-dvr-edge
exec /opt/ively/analog-dvr-edge/venv/bin/python -m agent.server --config /opt/ively/analog-dvr-edge/configs/dvr_channels.json --host 127.0.0.1 --port 8090
