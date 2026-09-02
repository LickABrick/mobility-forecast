"""Lifecycle and entity compatibility tests against Home Assistant 2026.8.1."""

from __future__ import annotations

from importlib.metadata import version

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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


async def test_entry_lifecycle_registers_unavailable_read_only_sensor(
    hass: HomeAssistant,
) -> None:
    """Let Home Assistant drive setup, state registration, and clean unload."""

    assert version("homeassistant") == "2026.8.1"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic lifecycle profile",
        data={
            CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_lifecycle"],
            CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
            CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
            CONF_PHYSICAL_EVENT_POLICY: "include",
            CONF_ONLINE_EVENT_POLICY: "exclude",
            CONF_ALL_DAY_EVENT_POLICY: "exclude",
            CONF_NO_LOCATION_EVENT_POLICY: "exclude",
        },
        version=1,
        minor_version=3,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_forecast_distance"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["unit_of_measurement"] == UnitOfLength.KILOMETERS
    assert "service_date" not in state.attributes
    assert "distance_p50_km" not in state.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(entry, "runtime_data")
    restored_state = hass.states.get(entity_id)
    assert restored_state is not None
    assert restored_state.state == STATE_UNAVAILABLE
    assert restored_state.attributes["restored"] is True
