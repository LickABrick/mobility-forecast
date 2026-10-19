from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from homeassistant.core import SupportsResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.locations import normalize


async def test_transient_day_retries_then_recovers(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    now = datetime.now(UTC).replace(hour=9)
    event = Appointment(now, now + timedelta(hours=1), normalize("52,5"), False, "one")
    calls = 0

    async def routes(call):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("PRIVATE")
        return {"routes": [{"distance": 10, "duration": 1}]}

    hass.services.async_register(
        "waze_travel_time",
        "get_travel_times",
        routes,
        supports_response=SupportsResponse.ONLY,
    )
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        return_value=[event],
    ):
        runtime._schedule_calendar(now)
        await runtime.calendar_task
        day = event.start.date()
        assert day in runtime.calendar_pending_days
        assert runtime.calendar_attempts[day] == 1
        runtime._schedule_calendar(now)
        assert calls == 1
        runtime.calendar_next_work = now - timedelta(seconds=1)
        runtime.calendar_retry_at[day] = now - timedelta(seconds=1)
        runtime._schedule_calendar(now)
        await runtime.calendar_task
        assert runtime.calendar_status == "ready"
        assert runtime.plans[day].complete and calls == 3
        assert runtime.calendar_metrics["last_failure"] is None
    await runtime.shutdown()


async def test_retry_exhaustion_is_bounded(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    now = datetime.now(UTC)
    event = Appointment(
        now, now + timedelta(minutes=5), normalize("52,5"), False, "one"
    )
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        return_value=[event],
    ):
        for _ in range(3):
            runtime.calendar_next_work = now - timedelta(seconds=1)
            runtime.calendar_retry_at[event.start.date()] = now - timedelta(seconds=1)
            runtime._schedule_calendar(now)
            await runtime.calendar_task
        assert not runtime.calendar_pending_days
        assert runtime.calendar_metrics["retry_exhausted"] == 1
        assert runtime.calendar_status == "routing_unavailable"
    await runtime.shutdown()
