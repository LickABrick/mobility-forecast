import asyncio
from unittest.mock import AsyncMock

from custom_components.mobility_forecast.ev.coordinator import EVRuntime


async def test_dirty_change_during_worker_is_not_lost(hass):
    runtime = object.__new__(EVRuntime)
    runtime.stopping = False
    runtime.dirty = True
    runtime.listeners = []
    runtime.result = {"status": "ready"}
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def update():
        calls.append(True)
        if len(calls) == 1:
            entered.set()
            await release.wait()

    runtime.update = update
    task = asyncio.create_task(runtime.worker())
    await entered.wait()
    runtime.dirty = True
    release.set()
    await task
    assert len(calls) == 2
    runtime.update = AsyncMock(side_effect=RuntimeError("PRIVATE"))
    runtime.dirty = True
    await runtime.worker()
    assert runtime.result["reason"] == "processing_error"
    assert runtime.result["recommendation"] is None
    assert "PRIVATE" not in str(runtime.result)
    runtime.update = AsyncMock()
    runtime.dirty = True
    await runtime.worker()
    runtime.update.assert_awaited_once()
