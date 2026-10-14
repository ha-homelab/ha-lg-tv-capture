#!/usr/bin/env python3
"""Build a deterministic installation ZIP from an explicit public inventory."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = Path("custom_components/lg_tv_capture")
FILES = (
    "__init__.py",
    "camera.py",
    "capture.py",
    "config_flow.py",
    "const.py",
    "manifest.json",
    "strings.json",
    "translations/en.json",
)


def read_regular(root: Path, relative: Path) -> bytes:
    """Reject linked or special package inputs, including linked parent folders."""
    path = root / relative
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"Linked package input: {relative}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"Not a regular package input: {relative}")
    if path.stat().st_size > 256 * 1024:
        raise ValueError(f"Oversized package input: {relative}")
    return path.read_bytes()


def package(root: Path, output: Path, source_sha: str) -> Path:
    """Never glob a user's directory or include tests, caches, or recordings."""
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ValueError("Expected a full source commit SHA")
    payload = {
        str(COMPONENT / name): read_regular(root, COMPONENT / name) for name in FILES
    }
    payload[str(COMPONENT / "LICENSE")] = read_regular(root, Path("LICENSE"))
    manifest = json.loads(payload[str(COMPONENT / "manifest.json")])
    version = manifest["version"]
    if manifest["domain"] != "lg_tv_capture" or not re.fullmatch(
        r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", version
    ):
        raise ValueError("Invalid integration identity or version")
    output.mkdir(parents=True, exist_ok=False)
    archive = output / f"lg-tv-capture-{version}.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            zipped.writestr(entry, data)
    with zipfile.ZipFile(archive) as zipped:
        if set(zipped.namelist()) != set(payload) or zipped.testzip():
            raise ValueError("Invalid archive inventory")
        for name, data in payload.items():
            if zipped.read(name) != data:
                raise ValueError(f"Archive verification failed: {name}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".sha256").write_text(f"{digest}  {archive.name}\n")
    metadata = {
        "schema": 1,
        "version": version,
        "source_sha": source_sha,
        "archive": archive.name,
        "sha256": digest,
        "files": len(payload),
    }
    (output / "lg-tv-capture.version.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    return archive


if __name__ == "__main__":
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    print(package(ROOT, ROOT / "release-dist", sha))
