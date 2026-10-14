#!/usr/bin/env python3
"""Validate the shipped changelog through the actual publication contract."""

import base64
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

import release_control
from package_release import COMPONENT, ROOT


class ReleaseNotesTests(unittest.TestCase):
    def test_current_version_can_publish_reviewed_notes(self):
        version = json.loads((ROOT / COMPONENT / "manifest.json").read_text())[
            "version"
        ]
        policy = json.loads((ROOT / ".release-policy.json").read_text())
        raw = (ROOT / "CHANGELOG.md").read_bytes()
        git_blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
        source = "a" * 40
        client = Mock()
        client.api.return_value = {
            "type": "file",
            "path": "CHANGELOG.md",
            "encoding": "base64",
            "content": base64.b64encode(raw).decode(),
            "size": len(raw),
            "sha": hashlib.sha1(git_blob, usedforsecurity=False).hexdigest(),
        }
        with patch.object(
            release_control, "source_policy_snapshot", return_value={"data": policy}
        ):
            for suffix in ("-beta.1", "-rc.1", ""):
                with self.subTest(channel=suffix or "stable"):
                    body = release_control.release_notes(
                        client, f"v{version}{suffix}", source, "Test provenance"
                    )
                    self.assertIn("### Upgrade", body)
                    self.assertIn("### Security", body)
                    self.assertIn("Test provenance", body)
        client.api.assert_called_with(f"contents/CHANGELOG.md?ref={source}")


if __name__ == "__main__":
    unittest.main()
