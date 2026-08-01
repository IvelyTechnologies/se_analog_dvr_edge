# Provisioning API

After install, analog DVR edge exposes a local HTTP API on port `8090`.

## Health

```bash
curl -s http://127.0.0.1:8090/health
```

## View Config

```bash
curl -s http://127.0.0.1:8090/config
```

## Update Config

```bash
curl -s -X POST http://127.0.0.1:8090/config \
  -H 'Content-Type: application/json' \
  --data-binary @/opt/ively/analog-dvr-edge/configs/dvr_channels.json
```

## Probe DVR Channels

```bash
curl -s -X POST http://127.0.0.1:8090/probe
```

## Start Or Reload Workers

```bash
curl -s -X POST http://127.0.0.1:8090/reload
```

## Stop Workers

```bash
curl -s -X POST http://127.0.0.1:8090/stop
```

## Status

```bash
curl -s http://127.0.0.1:8090/status
```
