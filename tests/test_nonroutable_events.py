from datetime import UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.mobility_forecast.calendar_manager import (
    normalize_events,
    preprocess_appointments,
)
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import Route, plan_journeys


@pytest.mark.parametrize(
    "location", [None, "", "Unknown venue", "online", "https://teams.example"]
)
async def test_nonroutable_never_requests(location):
    events = normalize_events(
        [
            {
                "start": "2026-01-01T09:00:00Z",
                "end": "2026-01-01T10:00:00Z",
                "location": location,
            }
        ],
        UTC,
    )
    selected, ignored = preprocess_appointments(events)
    assert selected == [] and ignored == 0
    provider = SimpleNamespace(get_route=AsyncMock())
    assert await plan_journeys(events, normalize("52,5"), provider) == {}
    provider.get_route.assert_not_called()


async def test_mixed_day_remains_one_chain():
    rows = [
        {
            "start": f"2026-01-01T{hour:02}:00:00Z",
            "end": f"2026-01-01T{hour + 1:02}:00:00Z",
            "location": location,
        }
        for hour, location in [
            (8, None),
            (10, "Office"),
            (12, "online"),
            (14, "53,6"),
            (16, None),
        ]
    ]
    events = normalize_events(rows, UTC, {"Office": "52,5"})
    selected, _ = preprocess_appointments(events)
    provider = SimpleNamespace(get_route=AsyncMock(return_value=Route(10, 1)))
    plans = await plan_journeys(selected, normalize("51,4"), provider)
    assert next(iter(plans.values())).distance_km == 30
    assert next(iter(plans.values())).complete
    assert provider.get_route.await_count == 3
