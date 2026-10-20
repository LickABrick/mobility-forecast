"""Change-aware agenda acceptance with bounded stale retention."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import Plan


async def test_24h_unchanged_then_edit_cancel_outage(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    start = datetime(2026, 3, 28, 0, tzinfo=UTC)
    target = start + timedelta(days=2, hours=9)
    events = [
        Appointment(
            target,
            target + timedelta(hours=1),
            normalize("52,5"),
            False,
            "title-not-routing-input",
        )
    ]

    def route(items, *args):
        return {items[0].start.date(): Plan(67, True)}

    async def cycle(now):
        runtime.calendar_days = None
        runtime.calendar_refreshed_at = now
        await runtime._refresh_calendar(now, runtime.calendar_generation)

    with (
        patch.object(runtime, "async_request_refresh"),
        patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            side_effect=lambda *args: events,
        ) as fetch,
        patch(
            "custom_components.mobility_forecast.routing._plan_journeys",
            side_effect=route,
        ) as itinerary,
    ):
        await cycle(start)
        for half_hour in range(1, 49):
            await cycle(start + timedelta(minutes=30 * half_hour))
        assert fetch.call_count == 49
        assert itinerary.call_count == 1
        assert runtime.plans[target.date()].distance_km == 67
        # Title changes and equivalent location spellings are irrelevant.
        events = [
            Appointment(
                target,
                target + timedelta(hours=1),
                normalize("52.0, 5.00"),
                False,
                "new-title",
            )
        ]
        await cycle(start + timedelta(days=1))
        assert itinerary.call_count == 1
        events = [
            Appointment(
                target,
                target + timedelta(hours=1),
                normalize("53,6"),
                False,
                "new-title",
            )
        ]
        await cycle(start + timedelta(days=1))
        assert itinerary.call_count == 2
        with patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            side_effect=TimeoutError,
        ):
            await cycle(start + timedelta(days=1, hours=1))
            assert runtime.calendar_status == "stale"
            assert target.date() in runtime.plans
            await cycle(start + timedelta(days=1, hours=3))
            assert not runtime.plans
        # Restore then authoritative cancellation removes the overlay.
        await cycle(start + timedelta(days=1, hours=3))
        events = []
        await cycle(start + timedelta(days=1, hours=4))
        assert not runtime.plans
    await runtime.shutdown()
