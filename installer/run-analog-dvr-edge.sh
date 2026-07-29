#!/usr/bin/env bash
set -euo pipefail
cd /opt/ively/analog-dvr-edge
exec /opt/ively/analog-dvr-edge/venv/bin/python -m agent.main --config /opt/ively/analog-dvr-edge/configs/dvr_channels.json
