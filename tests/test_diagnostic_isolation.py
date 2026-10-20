"""Two actual HA vehicles cannot share sync state or listener lifetime."""

import asyncio
from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_two_vehicle_diagnostic_isolation(hass):
    entries = [
        MockConfigEntry(
            domain=DOMAIN, title=name, data={"odometer": f"sensor.{name.lower()}"}
        )
        for name in ("First", "Second")
    ]
    for entry in entries:
        hass.states.async_set(
            entry.data["odometer"], "100", {"unit_of_measurement": "km"}
        )
        entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        for entry in entries:
            await entry.runtime_data.initialization_task
            await entry.runtime_data.import_task
        registry = er.async_get(hass)
        first, second = (entry.runtime_data for entry in entries)
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow():
            entered.set()
            await release.wait()

        first.manual_sync.cycle = slow
        first.manual_sync.trigger()
        await entered.wait()
        await second.manual_sync.request()

        def state(entry, key):
            entity = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}"
            )
            return hass.states.get(entity)

        assert state(entries[0], "sync_status").state == "syncing"
        assert state(entries[1], "sync_status").state == "idle"
        assert state(entries[0], "last_successful_sync").state == "unknown"
        assert state(entries[1], "last_successful_sync").state != "unknown"
        await hass.config_entries.async_unload(entries[0].entry_id)
        assert first.manual_sync.last_result == "interrupted"
        assert first.manual_sync.listeners == []
        assert first.manual_sync.task.done()
        assert not second.stopping
        await hass.config_entries.async_unload(entries[1].entry_id)
        assert second.manual_sync.listeners == []
