import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.coordinator import VehicleCoordinator


async def test_global_deadline_and_coalescing(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.odometer"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    now = datetime.now(UTC)

    async def slow(*args):
        await asyncio.Event().wait()

    with (
        patch(
            "custom_components.mobility_forecast.coordinator.CALENDAR_REFRESH_BUDGET",
            0.01,
        ),
        patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            side_effect=slow,
        ) as fetch,
    ):
        runtime._schedule_calendar(now)
        task = runtime.calendar_task
        runtime._schedule_calendar(now)
        assert runtime.calendar_task is task
        async with asyncio.timeout(1):
            await task
        assert runtime.calendar_status == "routing_unavailable"
        runtime._schedule_calendar(now)
        assert fetch.call_count == 1
        await runtime.shutdown()
