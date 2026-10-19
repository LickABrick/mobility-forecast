from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.history import merge_readings
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.routing import plan_journeys


def test_late_high_reading_cannot_evict_trusted_anchor():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    trusted = [Reading(now, 100), Reading(now + timedelta(days=2), 140)]
    result, rejected = merge_readings(trusted, [Reading(now + timedelta(days=1), 500)])
    assert result == trusted
    assert rejected == 1


async def test_nested_conflicting_events_no_impossible_chain():
    now = datetime(2026, 1, 1, 9, tzinfo=UTC)
    a, b = normalize("52,5"), normalize("53,6")
    events = [
        Appointment(now, now + timedelta(hours=5), a, False, "1"),
        Appointment(now + timedelta(hours=1), now + timedelta(hours=2), a, False, "2"),
        Appointment(now + timedelta(hours=3), now + timedelta(hours=4), b, False, "3"),
    ]
    provider = SimpleNamespace(get_route=AsyncMock())
    plans = await plan_journeys(events, a, provider)
    assert not plans[now.date()].complete
    provider.get_route.assert_not_called()
