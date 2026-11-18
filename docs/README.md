# Documentation

A Home Assistant integration and reusable module that captures a stream from an
LG TV, with the release and signature records around it.

## Design

- [Architecture](architecture.md) — how a camera request becomes an opted-in WebSocket request.

## Quality

- [Quality and assessment scope](quality.md) — the integration, capture module and packaging tools the assessment covers.
- [OpenSSF evidence](openssf-evidence.md) — the proposed Passing assessment in `.bestpractices.json`.

## Releases

- [Verify a signed release](release-signatures.md) — what `sign_releases: true` enables and how to check an artefact.
- [CI and release operations](release-workflow.md) — `.release-policy.json` and the required status.
- [Version plans and manifest synchronization](VERSIONING.md) — the versioning opt-in.
- [Release-candidate fuzzing](fuzzing.md) — the illustrated fuzzing process.
- [Fuzzing release candidates](rc-fuzzing.md) — the reusable bounded fuzz workflow.
- [Release read recovery and rerun validation](release-read-safety.md) — the two fixes carried from the shared toolkit.
- [Early final-build runner check](runner-preflight.md) — why the check runs before the final build.
