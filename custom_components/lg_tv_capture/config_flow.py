"""Select a TV already paired by Home Assistant's webOS integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import CONF_ALLOW_WEBSOCKET, CONF_SOURCE, DOMAIN


class LGTVCaptureConfigFlow(ConfigFlow, domain=DOMAIN):
    """One capture entry per registered television."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow selection without asking for an IP address or pairing key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            source = er.async_get(self.hass).async_get(user_input[CONF_SOURCE])
            if (
                not source
                or source.domain != "media_player"
                or source.platform != "webostv"
                or source.disabled
                or not source.config_entry_id
                or not (
                    paired := self.hass.config_entries.async_get_entry(
                        source.config_entry_id
                    )
                )
                or paired.domain != "webostv"
            ):
                errors[CONF_SOURCE] = "invalid_tv"
            else:
                await self.async_set_unique_id(source.id)
                self._abort_if_unique_id_configured()
                state = self.hass.states.get(source.entity_id)
                name = (
                    source.name
                    or source.original_name
                    or (state.name if state else paired.title)
                )
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_SOURCE: source.id,
                        CONF_ALLOW_WEBSOCKET: user_input.get(
                            CONF_ALLOW_WEBSOCKET, False
                        ),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            filter=selector.EntityFilterSelectorConfig(
                                domain="media_player", integration="webostv"
                            )
                        )
                    ),
                    vol.Optional(CONF_ALLOW_WEBSOCKET, default=False): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Allow WebSocket opt-in to be changed without selecting another TV."""
        return LGTVCaptureOptionsFlow()


class LGTVCaptureOptionsFlow(OptionsFlow):
    """Configure external WebSocket access."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        default = self.config_entry.options.get(
            CONF_ALLOW_WEBSOCKET,
            self.config_entry.data.get(CONF_ALLOW_WEBSOCKET, False),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_ALLOW_WEBSOCKET, default=default): bool}
            ),
        )
