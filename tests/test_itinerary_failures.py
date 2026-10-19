from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import Route, plan_journeys


@pytest.mark.parametrize(
    "minutes,reason", [(4, None), (5, None), (35, "impossible_itinerary")]
)
async def test_available_travel_time(minutes, reason):
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    events = [
        Appointment(start, start + timedelta(hours=1), normalize("52,5"), False, "a"),
        Appointment(
            start + timedelta(hours=1, minutes=5),
            start + timedelta(hours=2),
            normalize("53,6"),
            False,
            "b",
        ),
    ]
    provider = SimpleNamespace(get_route=AsyncMock(return_value=Route(10, minutes)))
    plan = (await plan_journeys(events, normalize("51,4"), provider))[start.date()]
    assert plan.reason == reason
    assert plan.complete is (reason is None)
    assert not plan.retryable
    if reason:
        assert plan.distance_km == 0


@pytest.mark.parametrize(
    "failure,reason", [(None, "route_unavailable"), ("route_timeout", "route_timeout")]
)
async def test_request_failures_are_retryable(failure, reason):
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    events = [
        Appointment(start, start + timedelta(hours=1), normalize("52,5"), False, "a")
    ]
    provider = SimpleNamespace(
        get_route=AsyncMock(return_value=None), last_failure=failure
    )
    plan = (await plan_journeys(events, normalize("51,4"), provider))[start.date()]
    assert plan.reason == reason and plan.retryable
