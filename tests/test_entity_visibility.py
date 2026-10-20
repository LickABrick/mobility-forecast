import asyncio
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN, FORECAST_KEYS


@pytest.mark.parametrize("value", [None, "unknown", "unavailable", "garbage", "100"])
async def test_learning_entities_exist_in_registry_and_states(hass, value):
    if value is not None:
        hass.states.async_set("sensor.odometer", value, {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain=DOMAIN, title="Car", data={"odometer": "sensor.odometer"}
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        entities = [
            e
            for e in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
            if not e.unique_id.endswith("_mileage_timeline")
        ]
        assert len(entities) == 5
        assert {e.unique_id for e in entities} == {
            f"{entry.entry_id}_{key}" for key in FORECAST_KEYS
        }
        assert len({e.device_id for e in entities}) == 1
        for entity in entities:
            assert entity.disabled_by is None
            state = hass.states.get(entity.entity_id)
            assert state is not None and state.state == "unknown"
            assert state.attributes["forecast_status"] in (
                "learning",
                "source_unavailable",
            )
        await hass.config_entries.async_unload(entry.entry_id)


async def test_slow_initialization_does_not_delay_registration(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"odometer": "sensor.odometer"})
    entry.add_to_hass(hass)

    async def slow(*args):
        await asyncio.Event().wait()

    with patch(
        "custom_components.mobility_forecast.storage.VehicleStore.load_readings",
        side_effect=slow,
    ):
        async with asyncio.timeout(1):
            assert await async_setup_component(hass, DOMAIN, {})
        entities = [
            e
            for e in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
            if not e.unique_id.endswith("_mileage_timeline")
        ]
        assert len(entities) == 5
        assert all(hass.states.get(e.entity_id).state == "unknown" for e in entities)
        await hass.config_entries.async_unload(entry.entry_id)


async def test_import_failure_keeps_states(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"odometer": "sensor.odometer"})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        side_effect=RuntimeError,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        assert entry.runtime_data.import_status == "failed"
        assert (
            len(
                [
                    e
                    for e in er.async_entries_for_config_entry(
                        er.async_get(hass), entry.entry_id
                    )
                    if not e.unique_id.endswith("_mileage_timeline")
                ]
            )
            == 5
        )
        await hass.config_entries.async_unload(entry.entry_id)
