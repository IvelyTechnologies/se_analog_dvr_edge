#!/usr/bin/env bash
set -euo pipefail

# Validate the DVR Edge pipeline after configuration without changing services.
# It is intentionally read-only: use it before leaving a customer site.

CONFIG_PATH="${1:-/opt/ively/analog-dvr-edge/configs/dvr_channels.json}"
STATUS_URL="${STATUS_URL:-http://127.0.0.1:8090/status}"
HLS_PORT="${HLS_PORT:-8888}"
RTSP_PORT="${RTSP_PORT:-8554}"

if [[ ! -r "$CONFIG_PATH" ]]; then
  echo "ERROR: DVR Edge config is not readable: $CONFIG_PATH" >&2
  exit 2
fi

readarray -t SETTINGS < <(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    config = json.load(source)

prefix = str(config["site_prefix"]).strip().lower().replace(" ", "_")
channels = (config.get("dvr") or {}).get("channels") or []
duration = str((config.get("mediamtx") or {}).get("hls_segment_duration", "2s"))
print(prefix)
print(duration)
for channel in channels:
    print(f"{prefix}_ch{int(channel)}_low")
PY
)

PREFIX="${SETTINGS[0]}"
SEGMENT_DURATION="${SETTINGS[1]}"
STREAMS=("${SETTINGS[@]:2}")
EXPECTED_WORKERS="${#STREAMS[@]}"
FAILED=0

echo "=== DVR Edge service ==="
systemctl is-active --quiet analog-dvr-edge || { echo "FAIL service=analog-dvr-edge"; FAILED=1; }
systemctl is-active --quiet mediamtx || { echo "FAIL service=mediamtx"; FAILED=1; }

echo "=== Runtime workers ==="
STATUS="$(curl -fsS --max-time 10 "$STATUS_URL" || true)"
if [[ -z "$STATUS" ]]; then
  echo "FAIL status endpoint unavailable"
  FAILED=1
else
  WORKER_COUNT="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("workers", [])))' <<<"$STATUS" 2>/dev/null || echo 0)"
  RUNNING="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("running", False)).lower())' <<<"$STATUS" 2>/dev/null || echo false)"
  echo "running=$RUNNING workers=$WORKER_COUNT expected=$EXPECTED_WORKERS"
  if [[ "$RUNNING" != "true" || "$WORKER_COUNT" != "$EXPECTED_WORKERS" ]]; then
    echo "FAIL publishers are not fully running"
    FAILED=1
  fi
fi

echo "=== Published streams ==="
for stream in "${STREAMS[@]}"; do
  echo "--- $stream ---"
  if ! timeout 15 ffprobe -v error -rtsp_transport tcp \
    "rtsp://127.0.0.1:${RTSP_PORT}/${stream}" \
    -show_entries stream=codec_name,width,height,r_frame_rate \
    -of default=nw=1; then
    echo "FAIL local_rtsp"
    FAILED=1
    continue
  fi

  jar="/tmp/dvr-edge-${stream}.cookies"
  rm -f "$jar"
  master="$(curl -fsSL --max-time 15 -c "$jar" -b "$jar" "http://127.0.0.1:${HLS_PORT}/${stream}/index.m3u8" || true)"
  variant="$(awk '!/^#/ && NF {print; exit}' <<<"$master")"
  if [[ -z "$variant" ]]; then
    echo "FAIL hls_master"
    FAILED=1
    continue
  fi

  playlist="$(curl -fsSL --max-time 15 -c "$jar" -b "$jar" "http://127.0.0.1:${HLS_PORT}/${stream}/${variant}" || true)"
  segment="$(awk '!/^#/ && NF {last=$0} END {print last}' <<<"$playlist")"
  if [[ -z "$segment" ]]; then
    echo "FAIL hls_playlist"
    FAILED=1
    continue
  fi

  result="$(curl -sSL --max-time 15 -c "$jar" -b "$jar" -o /dev/null \
    -w 'http=%{http_code} bytes=%{size_download} time=%{time_total}' \
    "http://127.0.0.1:${HLS_PORT}/${stream}/${segment}" || true)"
  echo "hls_segment $result"
  if [[ "$result" != http=200* ]]; then
    echo "FAIL hls_segment"
    FAILED=1
  elif [[ "$SEGMENT_DURATION" =~ ^[0-9]+s$ ]]; then
    elapsed="${result##*time=}"
    duration_seconds="${SEGMENT_DURATION%s}"
    if awk -v elapsed="$elapsed" -v duration="$duration_seconds" 'BEGIN { exit !(elapsed > duration) }'; then
      echo "WARN hls_segment_download_slower_than_${SEGMENT_DURATION}"
    fi
  fi
done

if (( FAILED )); then
  echo "RESULT=FAIL: do not leave the site until the failed layer is fixed."
  exit 1
fi

echo "RESULT=PASS: $PREFIX published $EXPECTED_WORKERS stream(s)."
