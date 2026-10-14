"""Home Assistant fixtures for the public integration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow the real HA loader to discover this custom integration."""
    yield


@pytest.fixture
async def television(hass: HomeAssistant):
    """A registered TV using a fake already-paired control transport."""
    client = SimpleNamespace(
        is_connected=Mock(return_value=True),
        connection=Mock(),
        request=AsyncMock(),
    )
    entry = MockConfigEntry(
        domain="webostv",
        title="Test TV",
        data={"host": "192.0.2.10", "client_secret": "test-only-placeholder"},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(client=client)
    registry = er.async_get(hass)
    source = registry.async_get_or_create(
        "media_player",
        "webostv",
        "test-tv",
        config_entry=entry,
        suggested_object_id="test_tv",
        original_name="Test TV",
    )
    hass.states.async_set(source.entity_id, "playing", {"source": "HDMI 1"})
    await hass.async_block_till_done()
    with (
        patch("homeassistant.components.webostv.async_setup_entry", return_value=True),
        patch("homeassistant.components.webostv.async_unload_entry", return_value=True),
    ):
        yield SimpleNamespace(entry=entry, source=source, client=client)
