# Quality and assessment scope

This assessment covers the Home Assistant integration, reusable capture module and packaging tools. It does not award a badge to
upstream Home Assistant, firmware, hosted platforms or downstream installations.

## Verification

Use the commands in [CONTRIBUTING](../CONTRIBUTING.md) and the current GitHub
Actions workflows. Keep the source commit, tool versions, command and outcome
with any evidence. A green job describes the checks it actually executed; a
path-filtered skipped job is not a fresh execution of those checks.

Compiler/safe-language warnings, static security analysis and dynamic tests have
different scopes. Document individual accepted warnings rather than disabling
rules globally. A successful simulated test or compilation does not establish
physical device behavior.

## Security argument

Home Assistant owns user authentication and the existing TV pairing. Screenshot access is separately authorized; downloads are same-host, bounded and pinned to the paired certificate. Frames stay in memory.

The security policy and implementation-specific tests describe the controls
for those boundaries. This is a compact engineering argument, not an independent
security certification or a completed formal assurance case.

## Current limits

Whole-project statement coverage of at least 80% has not been established by
this assessment. Test counts are not a coverage percentage. The maintainer has
confirmed knowledge of secure design and common vulnerability classes; knowledge
does not replace the implementation evidence. Governance records the absence of
a tested backup-maintainer/recovery arrangement, so Silver continuity is unmet.

Only a saved and verified public OpenSSF assessment establishes an awarded badge.
Missing evidence stays unmet until it is actually produced.

## Reviewed CodeQL quality diagnostics

The following five diagnostics on the initial source are code-quality warnings
with no security severity assigned. They are individually reviewed here, not
suppressed by disabling a rule. The generated release toolkit stays synchronized
with its upstream source.

- **17, constructor virtual call:** `scripts/merge_oci_archives.py` calls
  `validate_complete_graph` after populating the archive members, blobs, images
  and graph. `RuntimeArchive` initializes `descriptors` and `layer_names` before
  calling `super().__init__`; its override deliberately validates two platforms.
  No overridden method reads uninitialized subclass state.
- **18, constructor virtual call:** `EvidenceArchive` defines its own constructor
  and never calls `Archive.__init__`. It initializes `runtime` before its own
  call to `unchanged`; the suggested base-constructor path cannot occur.
- **14, unused import:** `custom_components/lg_tv_capture/const.py` deliberately
  re-exports `DOMAIN` using `from .capture import DOMAIN as DOMAIN`. Other
  integration modules import the constant from this public constants module.
- **2, mixed import:** `.github/release-tests/test_release_client_consumer.py`
  uses both `unittest.TestCase` and `from unittest import mock`. This accepted
  style warning has no behavioral impact; both imports are used.
- **1, unused local:** `.github/release-tests/test_release_control.py` passes
  `accepted_upload_then_failed_response` as the `side_effect` of `patch.object`.
  The callback simulates a committed upload followed by a failed API response;
  it is exercised by the release-client regression.

These five diagnostics are not five confirmed vulnerabilities. The integration's
Ruff check and the release contract tests remain enabled. A future upstream
toolkit cleanup can remove the cosmetic mixed-import warning.

## Assessment record — 2026-10-14

The current GitHub inventory found no non-PR issues, public project advisories
or open dependency alerts. Pull requests came from the maintainer and maintenance
bots. The maintainer confirmed no outside-GitHub bug, enhancement or vulnerability
reports in the preceding 12 months. Private vulnerability reporting is enabled.
Gitleaks scanned 11 available Git commits without a finding. These observations
are dated evidence, not a permanent guarantee or a claim of zero future defects.

Local verification passed 74 Home Assistant tests, 3 packaging tests, 1
changelog test and the configured Ruff checks. Tests use synthetic paired
certificates and disable network sockets.
