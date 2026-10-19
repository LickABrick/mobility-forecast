import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import CACHE_TTL, WazeProvider
from custom_components.mobility_forecast.storage import VehicleStore


def key(i):
    return hashlib.sha256(str(i).encode()).hexdigest()


@pytest.mark.parametrize(
    "bad",
    [
        {},
        None,
        [],
        {"at": "123", "km": 1, "minutes": 1},
        {"at": float("nan"), "km": 1, "minutes": 1},
        {"at": 1, "km": 0, "minutes": 0},
        {"at": True, "km": 1, "minutes": 1},
        {"at": 1, "km": float("inf"), "minutes": 1},
    ],
)
def test_invalid_cache_does_not_raise(bad):
    cache = {key(1): bad}
    WazeProvider(None, "eu", cache)
    assert cache == {}


async def test_expiration_refresh_and_storage_restart(hass):
    now = datetime.now(UTC).timestamp()
    cache = {
        key(1): {"at": now - CACHE_TTL - 1, "km": 1, "minutes": 1},
        key(2): {"at": now + 100, "km": 1, "minutes": 1},
    }
    services = SimpleNamespace(
        has_service=Mock(return_value=True),
        async_call=AsyncMock(
            return_value={"routes": [{"distance": 12, "duration": 3}]}
        ),
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu", cache)
    assert not cache
    a, b = normalize("52,5"), normalize("53,6")
    await provider.get_route(a, b)
    store = VehicleStore(hass, "cache-test")
    store.payload["routes"] = cache
    store.schedule_routes()
    await store.flush()
    restored = VehicleStore(hass, "cache-test")
    await restored.load_readings()
    await WazeProvider(
        SimpleNamespace(services=services), "eu", restored.payload["routes"]
    ).get_route(a, b)
    assert services.async_call.await_count == 1
    with patch("custom_components.mobility_forecast.routing.datetime") as clock:
        clock.now.return_value = SimpleNamespace(timestamp=lambda: now + CACHE_TTL + 10)
        fresh = WazeProvider(
            SimpleNamespace(services=services), "eu", restored.payload["routes"]
        )
        await fresh.get_route(a, b)
    assert services.async_call.await_count == 2
