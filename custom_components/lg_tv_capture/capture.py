"""Bounded, on-demand screenshots over an already paired webOS connection."""

from __future__ import annotations

import asyncio
import base64
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from time import monotonic, time
from typing import Any, NotRequired, TypedDict
from urllib.parse import urlsplit

from aiohttp import ClientTimeout, Fingerprint
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from PIL import Image

DOMAIN = "lg_tv_capture"
INTERVAL = 60
MAX_BYTES = 2_000_000
ACTIVE_STATES = frozenset({"on", "playing", "paused", "idle", "buffering"})


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


class Frame(TypedDict):
    """Public screenshot payload; timestamps are Unix seconds."""

    image: str | None
    captured_at: NotRequired[float]


@dataclass
class CaptureStore:
    """Process-local state; never persisted to a Home Assistant store."""

    captures: dict[str, TVCapture] = field(default_factory=dict)
    websocket_sources: dict[str, str] = field(default_factory=dict)


@callback
def get_store(hass: HomeAssistant) -> CaptureStore:
    """Return the shared store, including before any UI entry exists."""
    return hass.data.setdefault(DOMAIN, CaptureStore())


@callback
def get_capture(hass: HomeAssistant, entity_id: str) -> TVCapture:
    """Get a shared capture for trusted HA code; UI setup is not required.

    Call from the Home Assistant event loop. This function is not an external
    authorization boundary. Untrusted callers must use the opt-in WS command.
    """
    source = er.async_get(hass).async_get(entity_id)
    key = source.id if source else entity_id
    captures = get_store(hass).captures
    if key not in captures:
        if source and entity_id in captures:
            # A trusted integration can ask before webostv registers its entity.
            # Promote that object rather than splitting its lock/cooldown.
            captures[key] = captures.pop(entity_id)
            captures[key]._registry_id = source.id
        else:
            captures[key] = TVCapture(hass, entity_id)
    return captures[key]


async def async_get_frame(hass: HomeAssistant, entity_id: str) -> Frame:
    """Get a shared frame for trusted code, with the same one-minute cooldown."""
    return await get_capture(hass, entity_id).get()


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


class TVCapture:
    """Share a television's frame and failure cooldown across all viewers."""

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        self.hass = hass
        self._entity_id = entity_id
        entry = er.async_get(hass).async_get(entity_id)
        self._registry_id = entry.id if entry else None
        self.lock = asyncio.Lock()
        self.next_capture = 0.0
        self.playback: tuple[Any, ...] | None = None
        self.result: Frame = {"image": None}
        self._generation = 0
        # Observe transitions even when nobody asks for a frame, including an
        # A -> B -> A source transition during one cooldown.
        self._unsub: Callable[[], None] = hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._state_changed
        )

    @property
    def entity_id(self) -> str:
        """Resolve a registry ID on use so entity renames remain supported."""
        if self._registry_id:
            if entry := er.async_get(self.hass).async_get(self._registry_id):
                return entry.entity_id
        return self._entity_id

    @callback
    def _state_changed(self, event: Event) -> None:
        if event.data["entity_id"] not in (self.entity_id, self._entity_id):
            return
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if (
            old is None
            or new is None
            or old.state != new.state
            or old.attributes.get("source") != new.attributes.get("source")
            or old.attributes.get("restored") != new.attributes.get("restored")
        ):
            self._generation += 1
            self.result, self.playback = {"image": None}, None

    @callback
    def playback_identity(self) -> tuple[Any, ...] | None:
        """Fail closed when the source is inactive or the paired client changes."""
        state = self.hass.states.get(self.entity_id)
        if (
            not state
            or state.state not in ACTIVE_STATES
            or state.attributes.get("restored")
        ):
            return None
        try:
            client, _ = self.paired_client()
            if not client.is_connected() or client.connection is None:
                return None
            return (
                state.attributes.get("source", ""),
                state.last_changed,
                client.connection,
                self._generation,
            )
        except AttributeError, KeyError, TypeError, ValueError:
            return None

    async def get(self) -> Frame:
        """Return the current thumbnail or an empty result, without exceptions."""
        async with self.lock:
            playback = self.playback_identity()
            if playback is None:
                self.result, self.playback = {"image": None}, None
                return self.result.copy()
            if playback != self.playback:
                self.result, self.playback = {"image": None}, playback
            if monotonic() < self.next_capture:
                return self.result.copy()
            # Failed attempts and source changes do not bypass the rate limit.
            self.next_capture = monotonic() + INTERVAL
            try:
                async with asyncio.timeout(12):
                    image = await self.capture()
                if self.playback_identity() == playback:
                    self.result = {"image": image, "captured_at": time()}
            except Exception:  # Transport errors may contain private resource URLs.
                # Keep the old frame and original timestamp only for this source.
                # Cancellation is a BaseException and deliberately propagates.
                pass
            if self.playback_identity() != playback:
                self.result, self.playback = {"image": None}, None
            return self.result.copy()

    @callback
    def paired_client(self) -> tuple[Any, str]:
        """Borrow HA's existing control session; never create or pair a client."""
        registry_entry = er.async_get(self.hass).async_get(self.entity_id)
        if (
            not registry_entry
            or registry_entry.domain != "media_player"
            or registry_entry.platform != "webostv"
            or registry_entry.disabled
        ):
            raise ValueError("TV is not an enabled webOS media player")
        entry = self.hass.config_entries.async_get_entry(registry_entry.config_entry_id)
        if not entry or entry.domain != "webostv":
            raise ValueError("TV integration is unavailable")
        return entry.runtime_data.client, entry.data["host"]

    async def capture(self) -> str:
        """Take a screenshot and download it with the paired TLS certificate."""
        client, host = self.paired_client()
        if not client.is_connected():
            raise ValueError("TV is disconnected")
        tls = client.connection.get_extra_info("ssl_object")
        if not tls or not (certificate := tls.getpeercert(binary_form=True)):
            raise ValueError("Paired TLS connection required")
        fingerprint = paired_fingerprint(certificate)
        reply = await client.request("tv/executeOneShot")
        if not isinstance(reply, dict) or reply.get("returnValue") is not True:
            raise ValueError("TV capture failed")
        uri = capture_url(reply.get("imageUri", ""), host)
        session = async_get_clientsession(self.hass)
        async with session.get(
            uri,
            ssl=fingerprint,
            allow_redirects=False,
            auto_decompress=False,
            timeout=ClientTimeout(total=6),
        ) as response:
            if response.status != 200:
                raise ValueError("TV image unavailable")
            if (
                response.content_length is not None
                and response.content_length > MAX_BYTES
            ):
                raise ValueError("TV image exceeds limit")
            data = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("TV image exceeds limit")
        return await self.hass.async_add_executor_job(thumbnail, bytes(data))
