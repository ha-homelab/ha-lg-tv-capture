# Release-candidate fuzzing

This public repository uses the shared `venus-os-ci-toolkit` Atheris runner.
`.github/fuzz.json` declares the targets, dependency setup, production
instrumentation and time budgets. `.release-policy.json` pins the workflow and
runner to an immutable toolkit revision.

Mutation campaigns run only for an explicit **RC** dispatch on the public default
branch. Pull requests, pushes, beta and nightly releases run ordinary checks;
they do not spend minutes on mutation campaigns. Private forks cannot use the
public RC gate. This is repository-managed fuzzing, not enrollment in Google's
hosted OSS-Fuzz service.

## Targets and boundaries

- `capture-url` checks the real `capture_url` function with bounded JSON pairs.
  Accepted URLs must retain the paired hostname, HTTPS port 3001, exact capture
  path and no credentials, query, fragment or control characters. Assertions
  parse the accepted authority independently and reject altered URLs.
- `thumbnail` supplies synthetic or mutated JPEG bytes to the real `thumbnail`.
  Successful outputs must decode as bounded RGB JPEGs with no EXIF, ICC profile
  or JPEG comment. The corpus includes RGB/grayscale, metadata, truncation and
  oversized-dimension cases. No captured frames enter the corpus.
- `paired-certificate` exercises the real `paired_fingerprint` with synthetic
  DER certificates. It checks exact SHA-256 pinning and the declared RSA/EC/EdDSA
  strength policy. Fixed positive and negative samples include 2047/2048-bit RSA
  and P-192/P-224 boundaries. Certificates contain generated public test keys;
  their private keys are discarded and no real device identity is included.

The production functions live in `frame_validation.py`, which has no Home
Assistant dependency. The integration imports those same functions. The harness
imports that exact source through Atheris's normal import hook. Shared preflight
rejects missing or uninstrumented declared production functions before mutation.

Each target runs for 60 seconds with a 10-second per-input timeout and 2 GiB RSS
limit. URL JSON is capped at 8 KiB; JPEG and DER inputs at 64 KiB. The production
JPEG download limit remains 2 MB; large-file acceptance is covered separately by
ordinary tests. Dependency installation can access package registries; target
execution runs inside a Linux network namespace without network access. A run
with no real engine executions cannot qualify an RC.

The locked Atheris wheel uses CPython 3.12 on Linux x86-64. This exercises the
same pure Python source and locked Pillow/cryptography/aiohttp versions as the
application tests. Normal Home Assistant tests still run with the project's
Python 3.14 environment. This is not sanitizer instrumentation of every native
codec/cryptographic dependency, a TLS trust-chain audit, a live capture test or
firmware compatibility evidence.

## Local checks and reproduction

Cheap regression replay needs only the normal development environment:

```sh
uv sync --frozen
uv run --frozen python fuzz/replay.py
```

It checks known acceptance/rejection outcomes and replays every seed plus short
truncations. It also fails if Home Assistant was imported. Ordinary CI runs this
check without Atheris or a mutation campaign.

For mutation or instrumentation checks, use a disposable Linux x86-64 checkout
with CPython 3.12:

```sh
python3 -m venv .fuzz-venv
.fuzz-venv/bin/python -m pip install --require-hashes --only-binary=:all: -r .github/requirements-fuzz.txt
.fuzz-venv/bin/python fuzz/harness.py capture-url -max_len=8192 -max_total_time=60 -timeout=10 -rss_limit_mb=2048 fuzz/corpus/capture-url
.fuzz-venv/bin/python fuzz/harness.py thumbnail -max_len=65536 -max_total_time=60 -timeout=10 -rss_limit_mb=2048 fuzz/corpus/thumbnail
.fuzz-venv/bin/python fuzz/harness.py paired-certificate -max_len=65536 -max_total_time=60 -timeout=10 -rss_limit_mb=2048 fuzz/corpus/paired-certificate
```

For a failed RC, download its `fuzz-diagnostics-<attempt>` artifact and replay the
saved input with the corresponding target, for example:

```sh
.fuzz-venv/bin/python fuzz/harness.py thumbnail -runs=1 /path/to/saved-input
```

Retain a minimized synthetic regression seed and a deterministic expected-outcome
test with a fix. Never add screenshots, addresses, real certificates, tokens,
pairing data or Home Assistant configuration. Do not start the integration to
reproduce a fuzz result. Local checks do not replace a fresh qualified RC.

## Evidence and packaging

RC publication requires its own `fuzz-report.json` and
`release-inputs-fuzz.json`, bound to repository, source, run/attempt, manifest and
exact successful target set. Reports expose actual execution counts and the
shared runner's metrics; retained diagnostic logs and corpus support inspection.
See [the shared contract](rc-fuzzing.md) and [release rules](../RELEASING.md).

The installable ZIP allowlists integration files, including the production
`frame_validation.py`, and the MIT license. Harnesses, corpora and development
dependencies are excluded. Existing deterministic package tests verify this
inventory. Fuzzing never connects to a TV, Home Assistant, MQTT or any other
service, and it never installs or deploys the integration.
