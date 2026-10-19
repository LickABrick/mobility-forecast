import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import (
    MAX_CACHE,
    WazeProvider,
    plan_journeys,
)


@pytest.mark.parametrize("count", [150, 300])
async def test_five_work_locations(count):
    locations = [normalize(f"Main Street {i + 1}, Arnhem") for i in range(5)]
    home = normalize("52,5")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        Appointment(
            start + timedelta(days=i // (count // 30), hours=7 + i % (count // 30)),
            start
            + timedelta(
                days=i // (count // 30), hours=7 + i % (count // 30), minutes=30
            ),
            locations[i % 5],
            False,
            str(i),
        )
        for i in range(count)
    ]

    async def response(*args, **kwargs):
        await asyncio.sleep(0.001)
        return {"routes": [{"distance": 10, "duration": 0}]}

    services = SimpleNamespace(
        has_service=Mock(return_value=True), async_call=AsyncMock(side_effect=response)
    )
    hass = SimpleNamespace(services=services)
    cache = {}
    provider = WazeProvider(hass, "eu", cache)
    began = perf_counter()
    plans = await plan_journeys(events, home, provider)
    elapsed = perf_counter() - began
    stats = provider.statistics
    expected = 6 if count == 150 else 7
    assert services.async_call.await_count == expected
    assert len(plans) == 30 and all(p.complete for p in plans.values())
    print(
        f"five_locations count={count} elapsed={elapsed:.4f}s complete={len(plans)} pending=0 metrics={stats}"
    )
    second = WazeProvider(hass, "eu", cache)
    await plan_journeys(events, home, second)
    assert second.requests == 0
    assert services.async_call.await_count == expected


def test_expired_removed_before_capacity_eviction():
    now = datetime.now(UTC).timestamp()
    cache = {
        hashlib.sha256(str(i).encode()).hexdigest(): {
            "at": now - 10,
            "km": 1,
            "minutes": 1,
        }
        for i in range(MAX_CACHE)
    }
    expired = hashlib.sha256(b"expired").hexdigest()
    cache[expired] = {"at": 1, "km": 1, "minutes": 1}
    provider = WazeProvider(None, "eu", cache)
    assert len(cache) == MAX_CACHE and expired not in cache
    assert provider.statistics["route_cache_expired"] == 1
    assert provider.statistics["route_cache_evictions"] == 0


async def test_v1_formatting_key_reused_and_direction_values_independent():
    services = SimpleNamespace(
        has_service=Mock(return_value=True),
        async_call=AsyncMock(
            return_value={"routes": [{"distance": 15, "duration": 2}]}
        ),
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    a, b = normalize("52,5"), normalize("Main Street 10,Arnhem")
    legacy_key = provider.cache_key(a.identifier, "main street 10,arnhem")
    provider.cache[legacy_key] = {
        "at": datetime.now(UTC).timestamp(),
        "km": 9,
        "minutes": 1,
    }
    assert (await provider.get_route(a, b)).distance_km == 9
    assert (await provider.get_route(b, a)).distance_km == 15
    assert legacy_key in provider.cache
    assert provider.requests == 1


async def test_valid_cache_works_without_provider():
    services = SimpleNamespace(
        has_service=Mock(return_value=True),
        async_call=AsyncMock(
            return_value={"routes": [{"distance": 15, "duration": 2}]}
        ),
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    a, b = normalize("52,5"), normalize("53,6")
    await provider.get_route(a, b)
    services.has_service.return_value = False
    assert (await provider.get_route(a, b)).distance_km == 15
    assert await provider.get_route(b, a) is None
    assert provider.requests == 1
