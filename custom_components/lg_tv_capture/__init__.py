"""LG TV Capture: opt-in dashboard snapshots from paired webOS TVs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .capture import (
    TVCapture as TVCapture,
)
from .capture import (
    async_get_frame as async_get_frame,
)
from .capture import (
    get_capture as get_capture,
)
from .capture import (
    get_store,
)
from .const import CONF_ALLOW_WEBSOCKET, CONF_SOURCE, DOMAIN

PLATFORMS = [Platform.CAMERA]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the authenticated WebSocket command without contacting a TV."""
    get_store(hass)
    websocket_api.async_register_command(hass, websocket_get_frame)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an explicitly selected TV."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _update_websocket_source(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Revoke API access when the configured TV is unloaded."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        get_store(hass).websocket_sources.pop(entry.entry_id, None)
    return unloaded


@callback
def _update_websocket_source(hass: HomeAssistant, entry: ConfigEntry) -> None:
    store = get_store(hass)
    if entry.options.get(
        CONF_ALLOW_WEBSOCKET, entry.data.get(CONF_ALLOW_WEBSOCKET, False)
    ):
        store.websocket_sources[entry.entry_id] = entry.data[CONF_SOURCE]
    else:
        store.websocket_sources.pop(entry.entry_id, None)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _update_websocket_source(hass, entry)


@callback
def _authorized_source(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, entity_id: str
) -> bool:
    registry_entry = er.async_get(hass).async_get(entity_id)
    return bool(
        registry_entry
        and registry_entry.id in get_store(hass).websocket_sources.values()
        and connection.user
        and connection.user.permissions.check_entity(entity_id, POLICY_READ)
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "lg_tv_capture/get_frame",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_get_frame(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Read frames only for a configured source with explicit WebSocket opt-in."""
    entity_id = msg["entity_id"]
    if not _authorized_source(hass, connection, entity_id):
        connection.send_error(msg["id"], "unauthorized", "TV capture is not enabled")
        return
    frame = await async_get_frame(hass, entity_id)
    # An entry can be removed or access revoked while a TV request is in flight.
    if not _authorized_source(hass, connection, entity_id):
        connection.send_error(msg["id"], "unauthorized", "TV capture is not enabled")
        return
    connection.send_result(msg["id"], frame)
