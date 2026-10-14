# Contributing

Open an issue describing a reproducible problem or proposed change before a
large contribution. Include Home Assistant and TV firmware versions when
relevant, but remove IP addresses, pairing keys, camera tokens, resource URLs
and personal screenshots. Security reports belong in the private reporting
channel described in [SECURITY.md](SECURITY.md).

## Local development

Use Python 3.14.2 or newer and `uv`:

```sh
uv sync --frozen
uv run --frozen ruff check custom_components tests scripts/package_release.py
uv run --frozen ruff format --check custom_components tests
uv run --frozen pytest
python3 scripts/test_package_release.py
```

The test suite uses the real Home Assistant test framework with synthetic
images and a fake paired TV transport. It disables network access. Do not add
household configurations, secrets, real captured images or dependencies on a
particular TV to the automated suite. Keep new regression tests focused on
observable behavior and security boundaries.

Changes to the reusable `capture.py` must remain self-contained, with no
relative imports. Preserve `TVCapture`, `get_capture`, `async_get_frame` and
`thumbnail`, or explicitly document a breaking change. Do not weaken paired
TLS certificate pinning, same-host resource restrictions or capture limits.

Update the changelog for user-visible behavior. Keep `strings.json` and the
English translation aligned when changing the setup UI. Changes to the
minimum Home Assistant version should update `hacs.json`, documentation and
the locked test environment together.

## Releases

See [RELEASING.md](RELEASING.md). Release workflows and generated policy files
are managed by the shared release toolkit; edit its policy or source templates
rather than reformatting generated files. A passing automated suite does not
replace acceptance testing of the exact release on supported hardware.
