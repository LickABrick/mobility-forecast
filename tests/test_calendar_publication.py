from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from homeassistant.core import SupportsResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.locations import normalize


async def test_thirty_days_coalesce_first_and_final(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    now = datetime.now(UTC).replace(hour=9)
    events = [
        Appointment(
            now + timedelta(days=i),
            now + timedelta(days=i, hours=1),
            normalize("52,5"),
            False,
            str(i),
        )
        for i in range(30)
    ]
    published = []

    async def publish():
        published.append(len(runtime.plans))

    async def routes(call):
        return {"routes": [{"distance": 10, "duration": 1}]}

    hass.services.async_register(
        "waze_travel_time",
        "get_travel_times",
        routes,
        supports_response=SupportsResponse.ONLY,
    )
    with (
        patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            return_value=events,
        ),
        patch.object(runtime, "async_request_refresh", side_effect=publish),
    ):
        runtime._schedule_calendar(now)
        await runtime.calendar_task
        assert len(runtime.plans) == 30
        assert published[0] == 1
        assert published[-1] == 30
        assert len(published) == 2
        assert runtime.calendar_publish is None
    await runtime.shutdown()


async def test_shutdown_cancels_publication_timer(hass):
    entry = MockConfigEntry(domain="mobility_forecast", data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    runtime._queue_calendar_publish(runtime.calendar_generation)
    timer = runtime.calendar_publish
    await runtime.shutdown()
    assert timer.cancelled()
