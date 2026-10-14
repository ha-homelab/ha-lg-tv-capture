"""Pure validation of untrusted capture data, independent of Home Assistant."""

from __future__ import annotations

import base64
import re
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlsplit

from aiohttp import Fingerprint
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from PIL import Image

MAX_BYTES = 2_000_000


def paired_fingerprint(certificate: bytes) -> Fingerprint:
    """Pin the paired certificate only when its authentication key is strong.

    Pairing supplies trust, so a self-signed certificate is expected. This check
    does not replace that trust with a public CA or disable fingerprint matching.
    """
    key = x509.load_der_x509_certificate(certificate).public_key()
    if not (
        isinstance(key, rsa.RSAPublicKey)
        and key.key_size >= 2048
        or isinstance(key, ec.EllipticCurvePublicKey)
        and key.key_size >= 224
        or isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey))
    ):
        raise ValueError("Paired TLS certificate key is unsupported or too small")
    return Fingerprint(sha256(certificate).digest())


def capture_url(uri: str, host: str) -> str:
    """Accept only the paired host's exact HTTPS capture resource shape."""
    if not isinstance(uri, str) or not isinstance(host, str):
        raise ValueError("Unexpected TV capture URL")
    # Reject parser-normalized whitespace/control characters and escaped paths.
    if any(ord(char) <= 32 or ord(char) == 127 for char in uri):
        raise ValueError("Unexpected TV capture URL")
    url = urlsplit(uri)
    if (
        url.scheme != "https"
        or url.hostname != host.lower()
        or url.port != 3001
        or url.username is not None
        or url.password is not None
        or "?" in uri
        or "#" in uri
        or not re.fullmatch(r"/resources/[A-Za-z0-9_-]{1,128}/capture\.jpg", url.path)
    ):
        raise ValueError("Unexpected TV capture URL")
    return uri


def thumbnail(data: bytes) -> str:
    """Decode a complete bounded JPEG; re-encode without source metadata."""
    if (
        len(data) > MAX_BYTES
        or not data.startswith(b"\xff\xd8")
        or not data.endswith(b"\xff\xd9")
    ):
        raise ValueError("Incomplete or oversized TV JPEG")
    with Image.open(BytesIO(data)) as source:
        if source.format != "JPEG" or not (
            0 < source.width <= 1920 and 0 < source.height <= 1080
        ):
            raise ValueError("Unexpected TV image size or format")
        source.load()
        image = source.convert("RGB")
        image.thumbnail((480, 270))
        # A fresh pixel image also drops EXIF, ICC profiles and JPEG comments.
        clean = Image.new("RGB", image.size)
        clean.paste(image)
        output = BytesIO()
        clean.save(output, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()


