import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import WazeProvider


async def test_metrics_count_physical_calls_not_consumers():
    async def response(*args, **kwargs):
        await asyncio.sleep(0.001)
        return {"routes": [{"distance": 10, "duration": 1}]}

    services = SimpleNamespace(
        has_service=Mock(return_value=True), async_call=AsyncMock(side_effect=response)
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    a, b = normalize("52,5"), normalize("53,6")
    await asyncio.gather(*(provider.get_route(a, b) for _ in range(3)))
    await provider.get_route(a, b)
    await provider.get_route(a, a)
    stats = provider.statistics
    assert stats["route_lookups"] == 5
    assert stats["route_requests_deduplicated"] == 2
    assert stats["route_cache_hits"] == 1
    assert stats["route_cache_misses"] == 1
    assert stats["waze_requests"] == 1
    assert stats["waze_failures"] == 0
    assert stats["route_cache_entries"] == 1
    services.async_call.side_effect = RuntimeError("PRIVATE")
    assert await provider.get_route(b, a) is None
    assert provider.statistics["waze_failures"] == 1
    assert provider.statistics["route_cache_misses"] == 2
    assert provider.statistics["route_cache_entries"] == 1
