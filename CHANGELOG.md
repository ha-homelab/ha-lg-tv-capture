# Changelog

## [0.1.1] - Development line

- Add public-RC-only offline fuzzing for capture URLs, synthetic JPEGs and paired certificates, with ordinary CI regression replay and strict production-instrumentation checks.
- Move unchanged pure capture validation into a Home Assistant-independent module and include it in the installable package.
- Reject malformed or weak paired-TV certificates before requesting or downloading a screenshot. RSA requires at least 2048 bits, EC at least 224 bits; Ed25519/Ed448 are accepted. Update obsolete TV firmware/certificates instead of disabling verification.
- Document private reporting, governance, contribution rights and current OpenSSF evidence limits.


### Upgrade

Update through HACS or replace the integration directory with the release ZIP,
then restart Home Assistant. Existing LG webOS pairing and configuration are
retained; no data migration is needed. Home Assistant 2026.10.1 or newer remains
required. Update TV firmware if its paired certificate uses an obsolete weak key.

### Security

Capture downloads remain restricted to the paired television and its verified
certificate. The new offline fuzz targets validate URL restrictions, bounded
JPEG conversion and certificate key strength using synthetic inputs; they do
not contact televisions or grant additional network access. Captured frames
remain in memory.

## [0.1.0]

### Added

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

### Upgrade

This is the first standalone release. Install through HACS as a custom
integration or extract the release ZIP into the Home Assistant configuration
directory, then restart Home Assistant. Pair the television with the built-in
LG webOS integration before adding LG TV Capture.

### Security

Captures reuse the existing paired TLS connection and verify downloads against
its certificate. Image requests are authenticated, bounded, and restricted to
the paired television. Frames remain in memory; camera tokens and saved
snapshots should be treated as private. WebSocket screenshot access is opt-in.
