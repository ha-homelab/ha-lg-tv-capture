"""Transport, image and lifecycle tests, without a TV or network access."""

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import Fingerprint
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from homeassistant.helpers import entity_registry as er
from PIL import Image

from custom_components.lg_tv_capture import capture as api


def jpeg(size=(960, 540), **kwargs):
    output = BytesIO()
    Image.new("RGB", size, "#579bbc").save(output, format="JPEG", **kwargs)
    return output.getvalue()


def self_signed_certificate(key):
    """Create a synthetic paired-TV certificate without a trusted public CA."""
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "test-tv")])
    now = datetime.now(UTC)
    algorithm = None if isinstance(key, ed25519.Ed25519PrivateKey) else hashes.SHA256()
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, algorithm)
        .public_bytes(serialization.Encoding.DER)
    )


@pytest.fixture(scope="module")
def paired_certificate():
    return self_signed_certificate(rsa.generate_private_key(65537, 2048))


@pytest.fixture
def capture(hass, television):
    return api.get_capture(hass, television.source.entity_id)


@pytest.mark.parametrize(
    "uri",
    [
        "http://192.0.2.10:3001/resources/abcd/capture.jpg",
        "https://192.0.2.11:3001/resources/abcd/capture.jpg",
        "https://192.0.2.10:443/resources/abcd/capture.jpg",
        "https://192.0.2.10:3001/resources/abcd/capture.jpg?token=secret",
        "https://192.0.2.10:3001/resources/abcd/capture.jpg?",
        "https://192.0.2.10:3001/resources/abcd/capture.jpg#",
        "https://user@192.0.2.10:3001/resources/abcd/capture.jpg",
        "https://@192.0.2.10:3001/resources/abcd/capture.jpg",
        "https://192.0.2.10:3001/resources/../capture.jpg",
        "https://192.0.2.10:3001/resources/%61bcd/capture.jpg",
        "https://192.0.2.10:3001/resources/abcd/another.jpg",
        "https://192.0.2.10:3001/resources/abcd/capture.jpg\n",
        "https://192.0.2.10:bad/resources/abcd/capture.jpg",
        "https://192.0.2.10:3001/resources/" + "a" * 129 + "/capture.jpg",
        None,
    ],
)
def test_capture_url_rejects_untrusted_resources(uri):
    with pytest.raises(ValueError):
        api.capture_url(uri, "192.0.2.10")


@pytest.mark.parametrize("host", ["192.0.2.10", "tv.example", "2001:db8::10"])
def test_capture_url_accepts_only_paired_host(host):
    url_host = f"[{host}]" if ":" in host else host
    uri = f"https://{url_host}:3001/resources/abc_123-/capture.jpg"
    assert api.capture_url(uri, host) == uri


def test_thumbnail_is_small_and_strips_metadata():
    exif = Image.Exif()
    exif[270] = "Private source metadata"
    data_url = api.thumbnail(
        jpeg(exif=exif, comment=b"private", icc_profile=b"private")
    )
    assert data_url.startswith("data:image/jpeg;base64,")
    with Image.open(BytesIO(base64.b64decode(data_url.partition(",")[2]))) as image:
        assert image.size == (480, 270)
        assert image.getexif() == {}
        assert "icc_profile" not in image.info
        assert "comment" not in image.info


@pytest.mark.parametrize(
    "data",
    [
        b"not an image",
        jpeg()[:-10],
        jpeg((1921, 50)),
        jpeg((50, 1081)),
        b"\xff\xd8" + b"x" * 2_000_000 + b"\xff\xd9",
    ],
)
def test_thumbnail_rejects_oversized_or_broken_data(data):
    with pytest.raises((ValueError, OSError)):
        api.thumbnail(data)


async def test_shared_cache_and_concurrent_requests(hass, television, capture):
    assert capture is api.get_capture(hass, television.source.entity_id)
    capture.capture = AsyncMock(return_value="frame")
    results = await asyncio.gather(
        *(api.async_get_frame(hass, television.source.entity_id) for _ in range(8))
    )
    capture.capture.assert_awaited_once()
    assert all(result == results[0] for result in results)
    results[0]["image"] = "caller mutation"
    assert (await capture.get())["image"] == "frame"


async def test_failure_keeps_frame_and_original_timestamp(capture):
    capture.capture = AsyncMock(return_value="old")
    with patch.object(api, "monotonic", return_value=100):
        original = await capture.get()
    capture.capture.side_effect = RuntimeError("private URL must not escape")
    with patch.object(api, "monotonic", return_value=160):
        assert await capture.get() == original
    with patch.object(api, "monotonic", return_value=219.999):
        assert await capture.get() == original
    assert capture.capture.await_count == 2


async def test_exact_sixty_second_cooldown(capture):
    capture.capture = AsyncMock(return_value="frame")
    for instant in (100, 159.999):
        with patch.object(api, "monotonic", return_value=instant):
            await capture.get()
    capture.capture.assert_awaited_once()
    with patch.object(api, "monotonic", return_value=160):
        await capture.get()
    assert capture.capture.await_count == 2


async def test_failed_first_capture_is_throttled(capture):
    capture.capture = AsyncMock(side_effect=ValueError("failed"))
    assert await capture.get() == {"image": None}
    assert await capture.get() == {"image": None}
    capture.capture.assert_awaited_once()


async def test_source_and_power_transitions_clear_frame_without_viewers(
    hass, television, capture
):
    capture.capture = AsyncMock(return_value="frame")
    await capture.get()
    entity_id = television.source.entity_id
    hass.states.async_set(entity_id, "playing", {"source": "HDMI 2"})
    hass.states.async_set(entity_id, "playing", {"source": "HDMI 1"})
    await hass.async_block_till_done()
    assert await capture.get() == {"image": None}
    capture.next_capture = 0
    await capture.get()
    hass.states.async_set(entity_id, "off")
    hass.states.async_set(entity_id, "playing", {"source": "HDMI 1"})
    await hass.async_block_till_done()
    assert await capture.get() == {"image": None}
    assert capture.capture.await_count == 2


@pytest.mark.parametrize("state", ["off", "unavailable", "unknown", "standby"])
async def test_inactive_tv_does_not_capture(hass, television, capture, state):
    capture.capture = AsyncMock()
    hass.states.async_set(television.source.entity_id, state)
    assert await capture.get() == {"image": None}
    capture.capture.assert_not_awaited()


async def test_restored_missing_or_disconnected_tv_does_not_capture(
    hass, television, capture
):
    capture.capture = AsyncMock()
    hass.states.async_set(television.source.entity_id, "playing", {"restored": True})
    assert await capture.get() == {"image": None}
    hass.states.async_remove(television.source.entity_id)
    assert await capture.get() == {"image": None}
    hass.states.async_set(television.source.entity_id, "playing")
    television.client.is_connected.return_value = False
    assert await capture.get() == {"image": None}
    capture.capture.assert_not_awaited()


async def test_reconnect_invalidates_cached_frame(television, capture):
    capture.capture = AsyncMock(return_value="old")
    await capture.get()
    television.client.connection = Mock()
    assert await capture.get() == {"image": None}
    capture.capture.assert_awaited_once()


@pytest.mark.parametrize("fail", [False, True])
async def test_source_change_during_request_discards_result(
    hass, television, capture, fail
):
    capture.capture = AsyncMock(return_value="old")
    await capture.get()
    capture.next_capture = 0

    async def change_source():
        hass.states.async_set(
            television.source.entity_id, "playing", {"source": "HDMI 2"}
        )
        if fail:
            raise ValueError("failed")
        return "stale"

    capture.capture = change_source
    assert await capture.get() == {"image": None}


async def test_cancellation_propagates_and_reserves_cooldown(capture):
    capture.capture = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await capture.get()
    assert capture.next_capture > 0


async def test_rename_preserves_shared_cache_and_cooldown(hass, television, capture):
    registry = er.async_get(hass)
    registry.async_update_entity(
        television.source.entity_id, new_entity_id="media_player.renamed_tv"
    )
    assert api.get_capture(hass, "media_player.renamed_tv") is capture
    assert capture.entity_id == "media_player.renamed_tv"


@pytest.mark.parametrize("exception", [AttributeError, KeyError, ValueError, TypeError])
async def test_changed_private_ha_api_fails_closed(capture, exception):
    capture.paired_client = Mock(side_effect=exception("private details"))
    assert await capture.get() == {"image": None}


@pytest.fixture
def transport(television, paired_certificate):
    certificate = paired_certificate
    television.client.connection.get_extra_info.return_value = SimpleNamespace(
        getpeercert=Mock(return_value=certificate)
    )
    television.client.request.return_value = {
        "returnValue": True,
        "imageUri": "https://192.0.2.10:3001/resources/abcd/capture.jpg",
    }
    body = jpeg()

    class Content:
        async def iter_chunked(self, size):
            for i in range(0, len(body), 71):
                yield body[i : i + 71]

    response = AsyncMock()
    response.__aenter__.return_value = response
    response.status = 200
    response.content = Content()
    response.content_length = None
    session = SimpleNamespace(get=Mock(return_value=response))
    with patch.object(api, "async_get_clientsession", return_value=session):
        yield SimpleNamespace(
            session=session, response=response, certificate=certificate, body=body
        )


async def test_capture_pins_paired_certificate_and_disables_redirects(
    capture, television, transport
):
    assert (await capture.capture()).startswith("data:image/jpeg;base64,")
    television.client.request.assert_awaited_once_with("tv/executeOneShot")
    args = transport.session.get.call_args.kwargs
    assert isinstance(args["ssl"], Fingerprint)
    assert args["ssl"].fingerprint == sha256(transport.certificate).digest()
    assert args["allow_redirects"] is False
    assert args["auto_decompress"] is False
    assert args["timeout"].total == 6


@pytest.mark.parametrize("kind", ["rsa1024", "ec192", "malformed"])
async def test_weak_or_invalid_certificate_rejected_before_capture(
    capture, television, transport, kind
):
    if kind == "malformed":
        certificate = b"not a certificate"
    else:
        key = (
            rsa.generate_private_key(65537, 1024)
            if kind == "rsa1024"
            else ec.generate_private_key(ec.SECP192R1())
        )
        certificate = self_signed_certificate(key)
    tls = television.client.connection.get_extra_info.return_value
    tls.getpeercert.return_value = certificate
    assert await capture.get() == {"image": None}
    television.client.request.assert_not_awaited()
    transport.session.get.assert_not_called()


@pytest.mark.parametrize("kind", ["rsa2048", "ec224", "ed25519"])
def test_supported_certificate_is_pinned_without_requiring_public_ca(kind):
    key = {
        "rsa2048": lambda: rsa.generate_private_key(65537, 2048),
        "ec224": lambda: ec.generate_private_key(ec.SECP224R1()),
        "ed25519": ed25519.Ed25519PrivateKey.generate,
    }[kind]()
    certificate = self_signed_certificate(key)
    assert (
        api.paired_fingerprint(certificate).fingerprint == sha256(certificate).digest()
    )


@pytest.mark.parametrize("status", [301, 302, 403, 500])
async def test_http_errors_and_redirects_are_rejected(capture, transport, status):
    transport.response.status = status
    assert await capture.get() == {"image": None}


@pytest.mark.parametrize("declared_length", [None, 2_000_001])
async def test_body_limit_applies_with_and_without_content_length(
    capture, transport, declared_length
):
    transport.response.content_length = declared_length
    with patch.object(api, "MAX_BYTES", 100):
        assert await capture.get() == {"image": None}


@pytest.mark.parametrize("reply", [{}, {"returnValue": False}, None, []])
async def test_invalid_capture_reply_is_rejected(capture, television, transport, reply):
    television.client.request.return_value = reply
    assert await capture.get() == {"image": None}
    transport.session.get.assert_not_called()


async def test_plaintext_connection_is_rejected_before_capture(
    capture, television, transport
):
    television.client.connection.get_extra_info.return_value = None
    assert await capture.get() == {"image": None}
    television.client.request.assert_not_awaited()
    transport.session.get.assert_not_called()


async def test_unregistered_source_fails_closed(hass):
    hass.states.async_set("media_player.not_registered", "playing")
    assert await api.async_get_frame(hass, "media_player.not_registered") == {
        "image": None
    }


async def test_late_registration_reuses_early_capture(hass, television):
    entity_id = "media_player.late_tv"
    early = api.get_capture(hass, entity_id)
    source = er.async_get(hass).async_get_or_create(
        "media_player",
        "webostv",
        "late-tv",
        config_entry=television.entry,
        suggested_object_id="late_tv",
    )
    assert source.entity_id == entity_id
    assert api.get_capture(hass, entity_id) is early
    assert early._registry_id == source.id
    assert entity_id not in api.get_store(hass).captures
