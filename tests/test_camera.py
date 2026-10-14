"""The camera delegates to the shared cache only on image requests."""

import base64
from unittest.mock import AsyncMock

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_tv_capture.camera import LGTVCaptureCamera
from custom_components.lg_tv_capture.capture import get_capture
from custom_components.lg_tv_capture.const import CONF_SOURCE, DOMAIN


async def test_camera_uses_shared_capture(hass, television):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Test TV", data={CONF_SOURCE: television.source.id}
    )
    camera = LGTVCaptureCamera(hass, entry)
    assert camera.should_poll is False
    assert not camera.supported_features
    assert camera.extra_state_attributes == {
        "source_entity_id": television.source.entity_id
    }
    television.client.request.assert_not_awaited()
    capture = get_capture(hass, television.source.entity_id)
    capture.capture = AsyncMock(
        return_value="data:image/jpeg;base64,"
        + base64.b64encode(b"test-image").decode()
    )
    assert await camera.async_camera_image() == b"test-image"
    assert await camera.async_camera_image(1920, 1080) == b"test-image"
    capture.capture.assert_awaited_once()
    hass.states.async_set(television.source.entity_id, "off")
    assert await camera.async_camera_image() is None


async def test_removed_source_cannot_capture(hass, television):
    camera = LGTVCaptureCamera(
        hass, MockConfigEntry(domain=DOMAIN, data={CONF_SOURCE: television.source.id})
    )
    er.async_get(hass).async_remove(television.source.entity_id)
    assert await camera.async_camera_image() is None
