# Security and privacy

Screenshots can contain private TV content. Add a TV only if its screenshots
should be visible through Home Assistant. Use normal Home Assistant account,
dashboard and network access controls. Standard camera tokens can authorize
image access without an interactive sign-in; do not publish them.

The custom WebSocket command is separately disabled by default. It requires a
loaded integration entry with explicit WebSocket opt-in and a signed-in user
with read access to the selected TV media player. Authorization is rechecked
after capture so revocation during a request cannot deliver a late frame.

## Transport boundary

- The adapter borrows the existing built-in `webostv` paired client. It does not
  create a control socket, read or copy pairing secrets, re-pair, issue playback
  commands, or install TV software.
- The only TV command is `tv/executeOneShot`.
- Downloads must use HTTPS, the configured paired host, explicit port 3001 and
  `/resources/<1–128 ASCII letters, digits, underscores or hyphens>/capture.jpg`.
  Credentials, query strings, fragments, control characters and other paths are
  rejected. Redirects are disabled.
- Download TLS is pinned to the SHA-256 fingerprint of the certificate from
  the existing paired TLS control connection. It does not use `ssl=False` or a
  trust-all context. The existing pairing connection remains the trust anchor;
  this cannot protect against an already compromised pairing/session or TV.
- Requests have a 12-second overall timeout and a 6-second HTTP timeout.
  Responses are capped at 2,000,000 bytes, including responses without a
  `Content-Length`. HTTP decompression is disabled. JPEGs must have complete
  start/end markers and dimensions no greater than 1920 × 1080 before decoding.
  Decoding happens in Home Assistant's executor; outgoing JPEGs are at most
  480 × 270 with source metadata removed.

## Retention and limitations

The latest frame is held in process memory. It is not stored in recorder state,
files, diagnostics, telemetry or logs by this integration. A failed refresh
retains an unchanged source's previous frame until a later request succeeds or
the source becomes invalid. This means the last frame may be old; API consumers
should use `captured_at` when freshness matters.

State transitions clear the cached frame even without viewers. Connection
changes are checked before every access and after every attempt. A browser
may retain a previously rendered image after the backend discards it; this
integration cannot erase browser caches or screenshots saved by users.

Trusted Python integrations running inside Home Assistant can call the shared
capture API without a UI entry. That internal API is not an authorization
boundary: custom integrations already execute with Home Assistant's privileges.
External integrations should use the authenticated camera or opted-in WebSocket
API rather than exposing the internal helper through an unauthenticated route.

To report a suspected vulnerability, use [GitHub private vulnerability reporting](https://github.com/ha-homelab/ha-lg-tv-capture/security/advisories/new). Do not post credentials, camera tokens, resource
URLs, screenshots or private Home Assistant configuration in a public issue.

## Coordinated response

Use [the private GitHub report form](https://github.com/ha-homelab/ha-lg-tv-capture/security/advisories/new)
or **alvit.work@gmail.com** if that form is unavailable. Maintainers aim to
acknowledge within 14 days. Assess impact, reproduce with synthetic data, agree
on remediation/disclosure and prioritize critical issues over feature work.
Confirmed medium-or-higher vulnerabilities must be fixed and released promptly,
within 60 days of public disclosure; do not defer a critical fix to a feature release.
Supported fixes target the latest release and default branch. Security release
notes identify affected/fixed versions, mitigations and available advisory/CVE
identifiers. Credit the reporter unless they request anonymity.

This is the response policy, not a claim that reports were received or that
past response times were measured. Home Assistant owns user authentication and the existing TV pairing. Screenshot access is separately authorized; downloads are same-host, bounded and pinned to the paired certificate. Frames stay in memory.

## Paired certificate minimums

Before requesting a screenshot, the integration parses the paired certificate
and requires RSA keys of at least 2048 bits, EC keys of at least 224 bits, or
Ed25519/Ed448. Invalid DER and other key types fail closed. The same certificate
is pinned by SHA-256 for the HTTPS download. This preserves the existing
pairing trust anchor; it does not claim public-CA validation for a self-signed TV.
A TV with an obsolete key needs a firmware/certificate update; this integration
does not offer a weak-key bypass. Synthetic tests cover accepted RSA/EC/Ed25519
and rejected RSA-1024, EC-192 and malformed certificates before the command or
download is issued. Home Assistant supplies cryptography and aiohttp.
