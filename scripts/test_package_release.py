#!/usr/bin/env python3
"""Verify installable inventory, reproducibility and source path confinement."""

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from package_release import COMPONENT, FILES, ROOT, package


class PackageTests(unittest.TestCase):
    def test_deterministic_installable_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = package(ROOT, Path(tmp) / "first", "a" * 40)
            second = package(ROOT, Path(tmp) / "second", "a" * 40)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                expected = {str(COMPONENT / name) for name in (*FILES, "LICENSE")}
                self.assertEqual(set(archive.namelist()), expected)
                archive.extractall(Path(tmp) / "config")
            installed = Path(tmp) / "config" / COMPONENT
            self.assertEqual(
                (installed / "capture.py").read_bytes(),
                (ROOT / COMPONENT / "capture.py").read_bytes(),
            )
            metadata = json.loads(
                (first.parent / "lg-tv-capture.version.json").read_text()
            )
            self.assertEqual(
                metadata["sha256"], hashlib.sha256(first.read_bytes()).hexdigest()
            )

    def test_private_files_excluded_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            shutil.copytree(ROOT / COMPONENT, root / COMPONENT)
            shutil.copy(ROOT / "LICENSE", root / "LICENSE")
            (root / COMPONENT / "private-token.txt").write_text("not-a-real-secret")
            archive = package(root, Path(tmp) / "first", "a" * 40)
            with zipfile.ZipFile(archive) as zipped:
                self.assertFalse(
                    any("private-token" in name for name in zipped.namelist())
                )
            source = root / COMPONENT / "capture.py"
            source.unlink()
            source.symlink_to(ROOT / COMPONENT / "capture.py")
            with self.assertRaisesRegex(ValueError, "Linked"):
                package(root, Path(tmp) / "second", "a" * 40)

    def test_requires_full_source_commit(self):
        with self.assertRaises(ValueError):
            package(ROOT, Path("unused"), "main")


if __name__ == "__main__":
    unittest.main()
