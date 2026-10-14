"""Snapshot-only camera entities; no background screenshot polling."""

from __future__ import annotations

import base64
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capture import get_capture
from .const import CONF_SOURCE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose one screenshot camera for the selected registry entry."""
    async_add_entities([LGTVCaptureCamera(hass, entry)])


class LGTVCaptureCamera(Camera):
    """Request a shared thumbnail only when HA asks for an image."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:television"
    _attr_should_poll = False
    _attr_brand = "LG"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__()
        self.hass = hass
        self._source_id = entry.data[CONF_SOURCE]
        self._attr_unique_id = self._source_id
        self._attr_name = f"{entry.title} screen"
        self.content_type = "image/jpeg"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose only the current source ID; never image bytes or resource URLs."""
        source = er.async_get(self.hass).async_get(self._source_id)
        return {"source_entity_id": source.entity_id if source else None}

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return at most 480x270 pixels, regardless of requested resolution."""
        source = er.async_get(self.hass).async_get(self._source_id)
        if source is None:
            return None
        result = await get_capture(self.hass, source.entity_id).get()
        if image := result["image"]:
            return base64.b64decode(image.partition(",")[2], validate=True)
        return None
