# Changelog

## 0.1.0

- Add a Home Assistant configuration flow for TVs already paired through the
  built-in LG webOS Smart TV integration.
- Provide a snapshot camera and an optional authenticated WebSocket API.
- Share one in-memory frame and a 60-second capture/failure cooldown per TV.
- Invalidate frames on source, power and connection changes; preserve the
  original timestamp when an unchanged source's refresh fails.
- Pin downloads to the paired TLS certificate, restrict capture URLs, bound
  image downloads and return metadata-free JPEG thumbnails.
- Export a reusable capture core for trusted Home Assistant integrations.

Compatibility: requires Home Assistant 2026.10.1 or newer. Automated contracts
are tested against 2026.10.1. Screenshot availability depends on TV firmware
and app/content restrictions. Root access and developer mode are not required.
