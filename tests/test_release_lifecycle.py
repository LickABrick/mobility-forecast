from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN
from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.storage import VehicleStore


async def test_two_vehicles_reload_persistence_and_remove(hass):
    entries = []
    for index in (1, 2):
        source = f"sensor.odometer_{index}"
        hass.states.async_set(
            source,
            str(1000 * index),
            {"unit_of_measurement": "km", "state_class": "total_increasing"},
        )
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=f"Car {index}",
            data={"odometer": source},
            unique_id=source,
        )
        entry.add_to_hass(hass)
        entries.append(entry)
        store = VehicleStore(hass, entry.entry_id)
        store.schedule(
            [
                Reading(
                    datetime.now(UTC) - timedelta(days=1),
                    1000 * index - 20,
                    "live",
                    source,
                )
            ]
        )
        await store.flush()
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        first, second = [e.runtime_data for e in entries]
        assert first.readings[-1].km == 1000
        assert second.readings[-1].km == 2000
        assert first.data.values["today"] is None
        assert await hass.config_entries.async_reload(entries[0].entry_id)
        await hass.async_block_till_done()
        assert entries[0].runtime_data.readings[0].km == 980
        assert entries[1].runtime_data is second
        await hass.config_entries.async_remove(entries[0].entry_id)
        assert await VehicleStore(hass, entries[0].entry_id).async_load() is None
        assert hass.states.get("sensor.odometer_1") is not None
        assert entries[1].runtime_data.readings[-1].km == 2000
        assert await hass.config_entries.async_unload(entries[1].entry_id)


async def test_corrupt_storage_never_overwritten(hass):
    store = VehicleStore(hass, "bad")
    await store.async_save({"readings": [["invalid"]]})
    assert await store.load_readings() == []
    assert store.corrupt
    store.schedule([])
    await store.flush()
    assert (await store.async_load())["readings"] == [["invalid"]]


async def test_v1_partial_payload_compatible(hass):
    store = VehicleStore(hass, "legacy")
    await store.async_save(
        {"readings": [["2026-01-01T00:00:00+00:00", 100, "live", "sensor.odometer"]]}
    )
    readings = await store.load_readings()
    assert readings[0].km == 100
    assert store.payload["routes"] == {}
    await store.flush()
