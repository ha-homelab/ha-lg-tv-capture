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
python3 scripts/test_consumer_changelog.py
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

## Opt-in automatic approval

The `auto-approve` label opts an eligible maintainer or dependency PR into the
organization's shared, commit-pinned approval workflow. It reads GitHub metadata
only: it never checks out PR code or downloads PR artifacts. Dependabot uses
`GITHUB_TOKEN`; owner-authored PRs use the independent `californiantiramisu`
reviewer through the existing organization `BOT_PAT` secret. Repository access
to that selected secret and the bot's Write role are provisioned separately;
missing credentials fail closed. The secret value is never stored in this repo.

Automatic approval records maintainer opt-in, not a human code review. It may
precede CI completion. The protected `main` branch still requires the successful
**CI gate**, an up-to-date approval, and resolved review conversations before any
merge. The shared workflow rechecks the live PR head and base before approving.
