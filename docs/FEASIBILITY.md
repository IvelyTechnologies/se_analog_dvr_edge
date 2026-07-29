# Feasibility Decision

## Can we use analog DVR cameras?

Yes, but the method depends on DVR capability.

## Best Case

DVR supports per-channel RTSP. Then each analog camera becomes a normal RTSP source. This is clean and production-friendly.

## Fallback Case

DVR does not support per-channel RTSP, but HDMI output is available. Then we can use a USB HDMI capture card and split the DVR grid into virtual camera crops.

## Not Possible Case

If DVR has no RTSP, HDMI output is protected/unstable, or the displayed grid cannot be locked, then reliable individual camera streams are not possible from that DVR without changing DVR hardware/settings.

## What We Need From Site

- DVR brand and model
- DVR local IP
- DVR username/password
- Number of channels
- Whether RTSP/ONVIF is enabled
- Whether HDMI output can be locked to fixed 2x2/3x3 layout
- Mini PC has USB HDMI capture card connected or not
