import asyncio
from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_switch_cycle_off_is_not_cancel_and_reload(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Car", data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{entry.entry_id}_manual_sync"
        )
        assert hass.states.get(entity_id).state == "off"
        entered, release = asyncio.Event(), asyncio.Event()

        async def cycle():
            entered.set()
            await release.wait()

        runtime.manual_sync.cycle = cycle
        task = asyncio.create_task(
            hass.services.async_call(
                "switch", "turn_on", {"entity_id": entity_id}, blocking=True
            )
        )
        await entered.wait()
        assert hass.states.get(entity_id).state == "on"
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert hass.states.get(entity_id).state == "on"
        release.set()
        await task
        assert hass.states.get(entity_id).state == "off"
        assert hass.states.get(entity_id).attributes["status"] == "success"
        assert await hass.config_entries.async_reload(entry.entry_id)
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        assert hass.states.get(entity_id).state == "off"
        await hass.config_entries.async_unload(entry.entry_id)
