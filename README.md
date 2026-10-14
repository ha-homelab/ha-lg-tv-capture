# LG TV Capture

[![Fuzzing: RC only](https://img.shields.io/badge/Fuzzing-RC%20only-blue)](docs/fuzzing.md)

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15477/badge)](https://www.bestpractices.dev/en/projects/15477)

On-demand screenshots of an LG webOS television, exposed as a Home Assistant
snapshot camera. Reuses the TV connection already paired by Home Assistant's
built-in **LG webOS Smart TV** integration. No root access, developer mode,
second pairing, account, or cloud service is required.

This is an unofficial custom integration. The screenshot command and the
Home Assistant webOS client adapter are not stable public interfaces. Support
depends on TV firmware and the current app. Protected content may produce an
empty or black image; this integration does not bypass content protection.

## Install

Requires **Home Assistant 2026.10.1 or newer**. Automated tests target 2026.10.1;
future releases may require compatibility updates.

### HACS custom repository

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/ha-homelab/ha-lg-tv-capture` with type **Integration**.
3. Download **LG TV Capture** and restart Home Assistant.

This repository is installed as a custom repository; it is not claimed to be
part of HACS's default catalog.

### Manual installation

Copy `custom_components/lg_tv_capture` from this repository into your Home
Assistant `config/custom_components` directory, then restart Home Assistant.
The final path should be `config/custom_components/lg_tv_capture/manifest.json`.

Alternatively, download the versioned `lg-tv-capture-<version>.zip` release
asset and extract it into the Home Assistant configuration directory. The
archive contains the `custom_components/lg_tv_capture/` path; check that the
resulting folder is not nested inside an extra directory. Restart Home
Assistant after installing or upgrading. See [the release guide](RELEASING.md)
for artifact checksums and release details.

### Configure

1. Pair your television with the built-in
   [LG webOS Smart TV integration](https://www.home-assistant.io/integrations/webostv/).
2. Open **Settings → Devices & services → Add integration → LG TV Capture**.
3. Select the already paired TV. Repeat for additional televisions.
4. Leave WebSocket access off unless a custom dashboard needs it.
5. Add the new `camera` entity to a picture entity card, for example:

```yaml
type: picture-entity
entity: camera.test_tv_screen
camera_view: auto
show_name: true
show_state: false
```

Replace the illustrative camera ID with the entity Home Assistant creates.
Snapshots are at most 480 × 270 pixels. A visible dashboard may request images
more often, but each TV receives at most one capture attempt per 60 seconds.
The integration performs no background capture polling and provides no live
video or audio. Home Assistant's own camera services can also request images.

## Behavior

- Each television has one shared in-memory frame, lock and cooldown. Concurrent
  viewers reuse a single attempt. Failed attempts consume the same cooldown.
- A failed refresh retains the last successful frame and its original timestamp
  only while the source, power state and paired connection remain unchanged.
- Source changes, power transitions, restored/unavailable entities and replaced
  or disconnected control sessions invalidate the old frame. Returning to the
  same source does not restore a discarded image.
- Captures may temporarily be unavailable for the remainder of the cooldown
  after changing channels, inputs or apps.
- Nothing is written to image files or recorder state by this integration.
  A user can explicitly save a camera snapshot or pass one to another service;
  those services have their own retention behavior.

## Optional WebSocket API

Enable **Allow screenshot access through the WebSocket API** in the integration
entry's configuration/options. Authenticate with Home Assistant's normal
WebSocket API, then send:

```json
{"id": 1, "type": "lg_tv_capture/get_frame", "entity_id": "media_player.test_tv"}
```

The `entity_id` is the selected **TV media player**, not the camera entity.
Successful results contain either `{"image": null}` or a JPEG data URL in
`image` and a Unix timestamp in `captured_at`. The caller must have read access
to the TV, and that TV must have a currently loaded, opted-in capture entry.
Entry unload/removal and option revocation take effect before an in-flight
response is delivered. No arbitrary host or image URL can be submitted.

Standard camera access uses Home Assistant's camera authentication and camera
tokens. Treat those tokens, screenshots and dashboard access as sensitive.
WebSocket opt-in controls this integration's WebSocket command only; adding a
camera already authorizes the standard Home Assistant camera interface.

## Troubleshooting

First check that the built-in TV integration is connected and the TV is on.
Wait one minute after a source change or failed capture. Try an unprotected
input or app if a particular app returns a black image. A TV whose paired
session does not use TLS is unsupported: certificate verification is never
disabled to make a capture work. A firmware or Home Assistant change may stop
captures until the adapter is updated. Transport exceptions and resource URLs
are intentionally not logged by this integration.

See [architecture](docs/architecture.md) and [security](SECURITY.md) for the
adapter contract, data handling and limits.

## Development

Use Python 3.14.2 or newer and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --frozen
uv run pytest
uv run ruff check custom_components tests scripts/package_release.py
uv run ruff format --check custom_components tests
```

Tests use Home Assistant's real config-flow, entity and WebSocket framework
with a fake paired TV transport. Network access is disabled in the test suite.
No actual television or household configuration is included. Source is
licensed under [MIT](LICENSE).

## Releases and maintenance

CI checks the Home Assistant contracts, capture security boundaries, deterministic
installation archive, dependencies and CodeQL findings. Release candidates and
stable promotion use the same source-bound release process as the other
ha-homelab projects. See [release operations](docs/release-workflow.md).

Repository settings, required checks and release protection are managed in
[Terraform](https://github.com/4alvit/terraform-github-ha-homelab).

## Project practices

[Contribute](CONTRIBUTING.md) · [Governance](GOVERNANCE.md) ·
[Code of Conduct](CODE_OF_CONDUCT.md) · [Roadmap](ROADMAP.md) ·
[Quality and assessment scope](docs/quality.md)

## Release-candidate fuzzing

The public release pipeline qualifies each RC with bounded, offline Atheris
campaigns for capture URLs, synthetic JPEGs and paired-certificate validation.
Ordinary CI replays the synthetic regression corpus without mutation campaigns.
See [targets, limits and reproduction commands](docs/fuzzing.md). These checks
do not connect to a television or establish firmware compatibility.
