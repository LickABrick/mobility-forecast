"""Native options preserve unrelated configuration and isolate suggestions."""

from unittest.mock import patch

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.config_flow import MobilityOptions


@pytest.mark.parametrize("enabled", [True, False])
async def test_ev_menu_and_disable_preserves(hass, enabled):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={
            "ev_enabled": enabled,
            "soc_entity": "sensor.soc",
            "home_window_start": "22:00",
            "known_locations": {"Office": "52,5"},
        },
    )
    entry.add_to_hass(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["menu_options"] == ["vehicle", "calendars", "locations", "ev_menu"]
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "ev_menu"}
    )
    assert ("ev_advanced" in flow["menu_options"]) == enabled
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "ev"}
    )
    with patch(
        "custom_components.mobility_forecast.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"ev_enabled": False, "charging_mode": "home_only"}
        )
    assert result["data"]["soc_entity"] == "sensor.soc"
    assert result["data"]["home_window_start"] == "22:00"
    assert result["data"]["known_locations"] == {"Office": "52,5"}


async def test_same_device_suggestions_unique_and_available(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"soc_entity": "sensor.soc"},
    )
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    car = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "car")}
    )
    other = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "home_battery")}
    )
    registry = er.async_get(hass)
    for name, device, unit, cls in [
        ("soc", car, "%", "battery"),
        ("power", car, "kW", "power"),
        ("other_power", other, "kW", "power"),
    ]:
        registry.async_get_or_create(
            "sensor", "test", name, suggested_object_id=name, device_id=device.id
        )
        hass.states.async_set(
            f"sensor.{name}", "10", {"unit_of_measurement": unit, "device_class": cls}
        )
    options = MobilityOptions()
    with patch.object(
        MobilityOptions,
        "config_entry",
        new_callable=lambda: property(lambda self: entry),
    ):
        options.hass = hass
        assert options._entity_suggestions()["charging_power_entity"] == "sensor.power"
        hass.states.async_set(
            "sensor.power",
            "unavailable",
            {"unit_of_measurement": "kW", "device_class": "power"},
        )
        assert "charging_power_entity" not in options._entity_suggestions()
        assert "charging_power_entity" not in options._options()
