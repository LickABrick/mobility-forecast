"""Bounded job progress, outcomes, persistence and coalescing without network."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.mobility_forecast.manual_sync import ManualSync, SyncOutcome


@pytest.mark.parametrize("result", ["success", "partial", "error"])
async def test_completed_outcome_and_timestamp(hass, result):
    store = SimpleNamespace(payload={}, schedule_routes=Mock())
    owner = SimpleNamespace(hass=hass, store=store)
    controller = ManualSync(
        owner,
        AsyncMock(
            return_value=SyncOutcome(
                result, None if result == "success" else "routing_incomplete"
            )
        ),
    )
    assert controller.activity == "idle" and controller.last_result == "never_run"
    transitions = []
    controller.listeners.append(
        lambda: transitions.append((controller.activity, controller.phase))
    )
    task = controller.trigger()
    # HA may eagerly run a genuinely immediate cycle to completion inside trigger.
    assert transitions[0] == ("syncing", "initializing")
    await task
    assert controller.activity == "idle" and controller.last_result == result
    assert controller.duration_seconds is not None
    assert (controller.successful_at is not None) == (result == "success")
    assert ("last_successful_sync" in store.payload) == (result == "success")
    assert transitions[0] == ("syncing", "initializing")
    assert transitions[-1] == ("idle", None)
    restored = ManualSync(owner, AsyncMock())
    restored.restore(store.payload)
    assert restored.successful_at == controller.successful_at
    assert not restored.running
    previous = controller.successful_at
    controller.cycle = AsyncMock(
        return_value=SyncOutcome("partial", "routing_incomplete")
    )
    await controller.request()
    assert controller.successful_at == previous


async def test_followup_during_followup_not_lost(hass):
    entered = [asyncio.Event() for _ in range(3)]
    release = [asyncio.Event() for _ in range(3)]
    rounds = 0

    async def cycle():
        nonlocal rounds
        index = rounds
        rounds += 1
        entered[index].set()
        await release[index].wait()

    controller = ManualSync(SimpleNamespace(hass=hass), cycle)
    task = controller.trigger()
    for i in range(3):
        await entered[i].wait()
        assert controller.running
        if i < 2:
            assert controller.trigger() is task
        release[i].set()
    await task
    assert rounds == 3 and controller.last_result == "success"
    assert not controller.running


@pytest.mark.parametrize(
    "value", [None, 42, "invalid", "2026-01-01T00:00:00", "2999-01-01T00:00:00+00:00"]
)
async def test_invalid_restoration(hass, value):
    controller = ManualSync(SimpleNamespace(hass=hass), AsyncMock())
    controller.restore({"last_successful_sync": value})
    assert controller.successful_at is None
