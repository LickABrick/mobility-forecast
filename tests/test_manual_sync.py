"""Action-style switch: off while idle, on for one bounded cycle, never cancellation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.xfail(strict=True, reason="Manual sync controller not implemented")
async def test_manual_sync_coalesces_and_resets(hass):
    from custom_components.mobility_forecast.manual_sync import ManualSync

    entered, release = asyncio.Event(), asyncio.Event()

    async def cycle():
        entered.set()
        await release.wait()

    owner = SimpleNamespace(hass=hass)
    controller = ManualSync(owner, cycle)
    first = asyncio.create_task(controller.request())
    await entered.wait()
    assert controller.running
    second = asyncio.create_task(controller.request())
    release.set()
    await asyncio.gather(first, second)
    assert not controller.running
    assert controller.status == "success"
    await controller.close()


@pytest.mark.xfail(strict=True, reason="Manual sync controller not implemented")
async def test_failure_resets_without_exposing_exception(hass):
    from custom_components.mobility_forecast.manual_sync import ManualSync

    controller = ManualSync(
        SimpleNamespace(hass=hass), AsyncMock(side_effect=RuntimeError("PRIVATE"))
    )
    await controller.request()
    assert not controller.running
    assert controller.status == "error"
    assert controller.error == "sync_failed"
