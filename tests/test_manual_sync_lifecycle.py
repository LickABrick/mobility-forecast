import asyncio
from types import SimpleNamespace

import pytest

from custom_components.mobility_forecast.manual_sync import ManualSync


async def test_close_interrupts_and_other_vehicle_is_independent(hass):
    entered = asyncio.Event()

    async def slow():
        entered.set()
        await asyncio.Event().wait()

    async def fast():
        return

    first = ManualSync(SimpleNamespace(hass=hass), slow)
    second = ManualSync(SimpleNamespace(hass=hass), fast)
    request = asyncio.create_task(first.request())
    await entered.wait()
    await second.request()
    assert second.status == "success" and not second.running
    assert first.running
    await first.close()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert first.status == "interrupted" and not first.running
    await first.request()
    assert not first.running
    await second.close()


async def test_timeout_resets(hass):
    async def slow():
        await asyncio.Event().wait()

    controller = ManualSync(SimpleNamespace(hass=hass), slow)
    # Exercise real timeout behavior without waiting two minutes.
    from unittest.mock import patch

    original = asyncio.timeout
    with patch(
        "custom_components.mobility_forecast.manual_sync.asyncio.timeout",
        side_effect=lambda _: original(0.001),
    ):
        await controller.request()
    assert controller.status == "error" and not controller.running
    await controller.close()
