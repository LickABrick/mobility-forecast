"""Config-flow compatibility tests against Home Assistant 2026.8.1."""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.config_flow import DOMAIN
from custom_components.mobility_forecast.ha_calendar import CONF_CALENDAR_ENTITY_IDS
from custom_components.mobility_forecast.profile_config import (
    CONF_ALL_DAY_EVENT_POLICY,
    CONF_END_ANCHOR_ENTITY_ID,
    CONF_NO_LOCATION_EVENT_POLICY,
    CONF_ONLINE_EVENT_POLICY,
    CONF_PHYSICAL_EVENT_POLICY,
    CONF_START_ANCHOR_ENTITY_ID,
)
from custom_components.mobility_forecast.route_provider_config import (
    CONF_HIGHWAY_POLICY,
    CONF_ROUTE_PROVIDER,
    CONF_ROUTE_PROVIDER_API_KEY,
    CONF_TOLL_POLICY,
)

PLANNING_INPUT = {
    CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
    CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
    CONF_PHYSICAL_EVENT_POLICY: "include",
    CONF_ONLINE_EVENT_POLICY: "exclude",
    CONF_ALL_DAY_EVENT_POLICY: "exclude",
    CONF_NO_LOCATION_EVENT_POLICY: "exclude",
}
ROUTE_INPUT = {
    CONF_ROUTE_PROVIDER: "google_routes",
    CONF_ROUTE_PROVIDER_API_KEY: "synthetic-test-key",
    CONF_TOLL_POLICY: "avoid",
    CONF_HIGHWAY_POLICY: "allow",
}


async def test_user_flow_creates_explicit_synthetic_profile(
    hass: HomeAssistant,
) -> None:
    """Exercise selector schema and entry creation through HA's real flow manager."""

    assert version("homeassistant") == "2026.8.1"

    form: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "user"
    assert form["errors"] is None
    expected_input = {
        CONF_NAME: "Synthetic commute",
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
        **PLANNING_INPUT,
        **ROUTE_INPUT,
    }
    assert form["data_schema"](expected_input) == expected_input

    result: dict[str, Any] = await hass.config_entries.flow.async_configure(
        form["flow_id"], user_input=expected_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Synthetic commute"
    assert result["data"] == {
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
        **PLANNING_INPUT,
        **ROUTE_INPUT,
    }
    assert result["result"].version == 1
    assert result["result"].minor_version == 4


async def test_reconfigure_preserves_calendar_and_updates_explicit_policy(
    hass: HomeAssistant,
) -> None:
    """Exercise Home Assistant's real reconfigure update/reload helper."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic existing profile",
        data={CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_existing"]},
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    form: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "reconfigure"
    result: dict[str, Any] = await hass.config_entries.flow.async_configure(
        form["flow_id"], user_input={**PLANNING_INPUT, **ROUTE_INPUT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_existing"],
        **PLANNING_INPUT,
        **ROUTE_INPUT,
    }
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
