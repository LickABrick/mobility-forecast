import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.models import Reading


async def test_slow_routes_never_block_history_and_unload(hass):
    now = datetime.now(UTC)
    source = "sensor.odometer"
    hass.states.async_set(source, "2000", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": source},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    began = asyncio.Event()
    stopped = asyncio.Event()

    async def slow(*args):
        began.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    runtime.readings = [
        Reading(now - timedelta(days=30 - i), 800 + i * 40, "live", source)
        for i in range(30)
    ]
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        side_effect=slow,
    ):
        async with asyncio.timeout(1):
            forecast = await runtime._async_update_data()
            assert forecast.values["today"] is not None
            await began.wait()
            task = runtime.calendar_task
            await runtime._async_update_data()
            assert runtime.calendar_task is task
            assert not runtime.lock.locked()
        await runtime.shutdown()
        assert stopped.is_set()
        assert runtime.calendar_task.done()


async def test_configuration_generation_rejects_old_results(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.odometer"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    began = asyncio.Event()
    release = asyncio.Event()

    async def pending(*args):
        began.set()
        await release.wait()
        return []

    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        side_effect=pending,
    ):
        await runtime._async_update_data()
        await began.wait()
        hass.config_entries.async_update_entry(entry, options={})
        await runtime._async_update_data()
        release.set()
        await runtime.shutdown()
        assert runtime.plans == {}
        assert runtime.calendar_status == "disabled"
