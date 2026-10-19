import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import WazeProvider


async def test_cancel_first_consumer_preserves_shared_request():
    began = asyncio.Event()
    release = asyncio.Event()

    async def response(*args, **kwargs):
        began.set()
        await release.wait()
        return {"routes": [{"distance": 9, "duration": 1}]}

    services = SimpleNamespace(
        has_service=Mock(return_value=True), async_call=AsyncMock(side_effect=response)
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    a, b = normalize("52,5"), normalize("53,6")
    first = asyncio.create_task(provider.get_route(a, b))
    await began.wait()
    second = asyncio.create_task(provider.get_route(a, b))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert (await second).distance_km == 9
    assert services.async_call.await_count == 1
    assert provider.inflight == {} and provider.consumers == {}


async def test_cancel_all_and_recover():
    began = asyncio.Event()

    async def response(*args, **kwargs):
        began.set()
        await asyncio.Event().wait()

    services = SimpleNamespace(
        has_service=Mock(return_value=True), async_call=AsyncMock(side_effect=response)
    )
    provider = WazeProvider(SimpleNamespace(services=services), "eu")
    a, b = normalize("52,5"), normalize("53,6")
    first = asyncio.create_task(provider.get_route(a, b))
    await began.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert provider.inflight == {} and not provider.cache
    services.async_call.side_effect = None
    services.async_call.return_value = {"routes": [{"distance": 8, "duration": 1}]}
    assert (await provider.get_route(a, b)).distance_km == 8
    await provider.async_close()
