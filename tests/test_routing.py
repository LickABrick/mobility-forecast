from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import (
    Route,
    WazeProvider,
    plan_journeys,
)


@pytest.mark.parametrize(
    "response,expected",
    [
        ({"routes": [{"distance": 20, "duration": 15}]}, 20),
        ({"routes": []}, None),
        ({"routes": [{}]}, None),
        ({"routes": [{"distance": -1, "duration": 5}]}, None),
    ],
)
async def test_waze(response, expected):
    services = SimpleNamespace(
        has_service=Mock(return_value=True), async_call=AsyncMock(return_value=response)
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    origin, destination = normalize("52,5"), normalize("53,6")
    result = await provider.get_route(origin, destination)
    assert (result.distance_km if result else None) == expected
    if result:
        await provider.get_route(origin, destination)
        assert services.async_call.await_count == 1
        assert result.duration_minutes == 15


async def test_chain_not_roundtrips():
    home, office, customer = [normalize(s) for s in ("52,5", "53,6", "54,7")]
    distances = {(home, office): 20, (office, customer): 35, (customer, home): 45}

    async def route(a, b):
        return Route(distances[a, b], 10)

    provider = SimpleNamespace(get_route=route)
    events = [
        Appointment(
            datetime(2026, 1, 1, h, tzinfo=UTC),
            datetime(2026, 1, 1, h + 1, tzinfo=UTC),
            location,
            False,
            str(h),
        )
        for h, location in [(9, office), (12, customer)]
    ]
    plan = (await plan_journeys(events, home, provider))[events[0].start.date()]
    assert plan.distance_km == 100
    assert plan.complete


async def test_unavailable_and_exception():
    services = SimpleNamespace(
        has_service=Mock(return_value=False), async_call=AsyncMock()
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    assert await provider.get_route(normalize("52,5"), normalize("53,6")) is None
    services.async_call.assert_not_called()
    services.has_service.return_value = True
    services.async_call.side_effect = TimeoutError
    assert await provider.get_route(normalize("52,5"), normalize("53,6")) is None
