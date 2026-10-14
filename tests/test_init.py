"""Entry lifecycle and the authenticated, explicitly opted-in WebSocket API."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import lg_tv_capture
from custom_components.lg_tv_capture.capture import get_store
from custom_components.lg_tv_capture.const import (
    CONF_ALLOW_WEBSOCKET,
    CONF_SOURCE,
    DOMAIN,
)


async def test_setup_and_unload(hass, television):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SOURCE: television.source.id, CONF_ALLOW_WEBSOCKET: True},
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await lg_tv_capture.async_setup_entry(hass, entry)
        assert get_store(hass).websocket_sources == {
            entry.entry_id: television.source.id
        }
        television.client.request.assert_not_awaited()
        assert await lg_tv_capture.async_unload_entry(hass, entry)
        assert get_store(hass).websocket_sources == {}


async def test_full_camera_platform_setup(hass, television):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test TV",
        data={CONF_SOURCE: television.source.id, CONF_ALLOW_WEBSOCKET: False},
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    cameras = hass.states.async_all("camera")
    assert len(cameras) == 1
    assert cameras[0].attributes["source_entity_id"] == television.source.entity_id
    television.client.request.assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.fixture
async def ws_client(hass, hass_ws_client):
    assert await async_setup_component(hass, "websocket_api", {})
    await lg_tv_capture.async_setup(hass, {})
    return await hass_ws_client(hass)


async def test_websocket_denies_unconfigured_tv(hass, television, ws_client):
    await ws_client.send_json(
        {
            "id": 1,
            "type": "lg_tv_capture/get_frame",
            "entity_id": television.source.entity_id,
        }
    )
    result = await ws_client.receive_json()
    assert result["success"] is False
    assert result["error"]["code"] == "unauthorized"
    television.client.request.assert_not_awaited()


async def test_websocket_opt_in_and_revocation(hass, television, ws_client):
    get_store(hass).websocket_sources["test-entry"] = television.source.id
    with patch.object(
        lg_tv_capture, "async_get_frame", new=AsyncMock(return_value={"image": None})
    ) as get_frame:
        await ws_client.send_json(
            {
                "id": 1,
                "type": "lg_tv_capture/get_frame",
                "entity_id": television.source.entity_id,
            }
        )
        result = await ws_client.receive_json()
        assert result["success"] is True
        assert result["result"] == {"image": None}
        get_frame.assert_awaited_once_with(hass, television.source.entity_id)
        get_store(hass).websocket_sources.clear()
        await ws_client.send_json(
            {
                "id": 2,
                "type": "lg_tv_capture/get_frame",
                "entity_id": television.source.entity_id,
            }
        )
        assert (await ws_client.receive_json())["error"]["code"] == "unauthorized"
        assert get_frame.await_count == 1


async def test_websocket_revocation_during_capture(hass, television, ws_client):
    get_store(hass).websocket_sources["test-entry"] = television.source.id

    async def revoke(*args):
        get_store(hass).websocket_sources.clear()
        return {"image": "secret screenshot", "captured_at": 123}

    with patch.object(lg_tv_capture, "async_get_frame", new=revoke):
        await ws_client.send_json(
            {
                "id": 1,
                "type": "lg_tv_capture/get_frame",
                "entity_id": television.source.entity_id,
            }
        )
        result = await ws_client.receive_json()
        assert result["success"] is False
        assert "secret screenshot" not in str(result)


async def test_websocket_respects_entity_permissions(hass, television, ws_client):
    get_store(hass).websocket_sources["test-entry"] = television.source.id
    with patch(
        "homeassistant.auth.permissions.PolicyPermissions.check_entity",
        return_value=False,
    ):
        await ws_client.send_json(
            {
                "id": 1,
                "type": "lg_tv_capture/get_frame",
                "entity_id": television.source.entity_id,
            }
        )
        result = await ws_client.receive_json()
        assert result["success"] is False
        television.client.request.assert_not_awaited()
