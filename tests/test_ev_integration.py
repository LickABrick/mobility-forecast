from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.ev.sensor import DESCRIPTIONS


async def test_ev_sensors_api_and_unload(hass):
    hass.states.async_set("sensor.soc", "40", {"unit_of_measurement": "%"})
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={
            "ev_enabled": True,
            "soc_entity": "sensor.soc",
            "usable_capacity_kwh": 60,
            "consumption_kwh_per_100km": 20,
            "max_ac_charge_power_kw": 11,
            "charging_mode": "home_only",
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, "mobility_forecast", {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        await runtime.ev.update()
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        for key in DESCRIPTIONS:
            entity = registry.async_get_entity_id(
                "sensor", "mobility_forecast", f"{entry.entry_id}_{key}"
            )
            assert hass.states.get(entity) is not None
        result = await hass.services.async_call(
            "mobility_forecast",
            "get_ev_plan",
            {"entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
        assert result["estimated_range_km"] == 75
        assert result["telemetry"]["freshness"] == "fresh"
        assert runtime.ev.http.requests == 0
        await hass.config_entries.async_unload(entry.entry_id)
        assert runtime.ev.stopping
