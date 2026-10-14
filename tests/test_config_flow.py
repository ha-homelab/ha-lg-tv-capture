"""Run config and options flows through the real Home Assistant framework."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_tv_capture.const import (
    CONF_ALLOW_WEBSOCKET,
    CONF_SOURCE,
    DOMAIN,
)


async def test_user_flow_and_duplicate(hass, television):
    with patch(
        "custom_components.lg_tv_capture.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        created = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SOURCE: television.source.entity_id}
        )
        assert created["type"] is FlowResultType.CREATE_ENTRY
        assert created["title"] == "Test TV"
        assert created["data"] == {
            CONF_SOURCE: television.source.id,
            CONF_ALLOW_WEBSOCKET: False,
        }
        assert created["result"].unique_id == television.source.id
        await hass.async_block_till_done()
        duplicate = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_SOURCE: television.source.entity_id},
        )
        assert duplicate["type"] is FlowResultType.ABORT
        assert duplicate["reason"] == "already_configured"
        television.client.request.assert_not_awaited()


async def test_invalid_source(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_SOURCE: "media_player.not_a_paired_tv"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SOURCE: "invalid_tv"}


async def test_options_flow(hass, television):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=television.source.id,
        data={CONF_SOURCE: television.source.id, CONF_ALLOW_WEBSOCKET: False},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ALLOW_WEBSOCKET: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_ALLOW_WEBSOCKET: True}
