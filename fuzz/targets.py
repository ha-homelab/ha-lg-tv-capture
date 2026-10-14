"""Bounded offline oracles around the exact production validation functions."""

from __future__ import annotations

import base64
import json
import re
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from PIL import Image

# Import the real source file without loading Home Assistant's integration entry.
# The mutation runner imports this module inside Atheris's import hook.
SOURCE = Path(__file__).resolve().parents[1] / "custom_components/lg_tv_capture"
sys.path.insert(0, str(SOURCE))
import frame_validation as production  # noqa: E402


def capture_url(data: bytes) -> None:
    if len(data) > 8192:
        return
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError):
        return
    if not isinstance(value, list) or len(value) != 2:
        return
    uri, host = value
    try:
        result = production.capture_url(uri, host)
    except ValueError:
        return
    assert result == uri
    assert isinstance(uri, str) and isinstance(host, str)
    assert all(ord(char) > 32 and ord(char) != 127 for char in uri)
    scheme, separator, location = uri.partition("://")
    assert separator and scheme.lower() == "https"
    authority, separator, path = location.partition("/")
    assert separator and "@" not in authority and "?" not in uri and "#" not in uri
    if authority.startswith("["):
        authority_host, close, port = authority[1:].partition("]")
        assert close and port.startswith(":")
        port = port[1:]
    else:
        authority_host, separator, port = authority.rpartition(":")
        assert separator
    assert authority_host.lower() == host.lower() and int(port) == 3001
    assert re.fullmatch(r"resources/[A-Za-z0-9_-]{1,128}/capture\.jpg", path)
    # Every accepted URL must reject these unequivocal authority/path changes.
    for altered in (uri + "?", uri + "#", uri + "/extra", "http" + uri[5:]):
        try:
            production.capture_url(altered, host)
        except ValueError:
            continue
        raise AssertionError("altered capture URL was accepted")


def thumbnail(data: bytes) -> None:
    if len(data) > 65536:
        return
    try:
        result = production.thumbnail(data)
    except (ValueError, OSError, Image.DecompressionBombError):
        return
    prefix = "data:image/jpeg;base64,"
    assert result.startswith(prefix)
    decoded = base64.b64decode(result[len(prefix):], validate=True)
    with Image.open(BytesIO(decoded)) as image:
        image.load()
        assert image.format == "JPEG" and image.mode == "RGB"
        assert 0 < image.width <= 480 and 0 < image.height <= 270
        assert not image.getexif()
        assert "icc_profile" not in image.info and "comment" not in image.info
    with Image.open(BytesIO(data)) as original:
        assert original.format == "JPEG"
        assert 0 < original.width <= 1920 and 0 < original.height <= 1080
        assert data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")


def paired_certificate(data: bytes) -> None:
    if len(data) > 65536:
        return
    try:
        certificate = x509.load_der_x509_certificate(data)
        key = certificate.public_key()
    except (ValueError, x509.InvalidVersion, UnsupportedAlgorithm):
        try:
            production.paired_fingerprint(data)
        except ValueError:
            return
        raise AssertionError("malformed certificate accepted") from None
    expected = (
        isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048
        or isinstance(key, ec.EllipticCurvePublicKey) and key.key_size >= 224
        or isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey))
    )
    try:
        fingerprint = production.paired_fingerprint(data)
    except ValueError:
        assert not expected, "supported strong certificate rejected"
        return
    assert expected, "weak or unsupported authentication key accepted"
    assert fingerprint.fingerprint == sha256(data).digest()


TARGETS = {
    "capture-url": capture_url,
    "thumbnail": thumbnail,
    "paired-certificate": paired_certificate,
}
