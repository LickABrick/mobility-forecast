"""Real coordinator/action diagnostics for partial, failed and source-error jobs."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN
from custom_components.mobility_forecast.manual_sync import SyncOutcome
from custom_components.mobility_forecast.routing import Plan


@pytest.mark.parametrize(
    "status,expected,code",
    [
        ("partial", "partial", "routing_budget_exceeded"),
        ("incomplete", "partial", "routing_incomplete"),
        ("routing_unavailable", "error", "routing_unavailable"),
        ("stale", "error", "calendar_fetch_failed"),
    ],
)
async def test_pipeline_incomplete(hass, status, expected, code):
    hass.states.async_set("sensor.car", "100", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.mobility_forecast.coordinator.import_history",
            return_value=[],
        ),
        patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            return_value=[],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        await runtime.calendar_task

        async def refresh():
            runtime.calendar_status = status
            runtime.calendar_pending_days = (
                {runtime.data.generated_at.date()} if status == "partial" else set()
            )

        with patch.object(runtime, "async_refresh", side_effect=refresh):
            with pytest.raises(HomeAssistantError, match=code):
                await hass.services.async_call(
                    DOMAIN, "sync_now", {"entry_id": entry.entry_id}, blocking=True
                )
        assert runtime.manual_sync.last_result == expected
        assert runtime.manual_sync.successful_at is None
        await hass.config_entries.async_unload(entry.entry_id)


async def test_action_waits_shares_switch_and_errors_are_private(hass):
    hass.states.async_set("sensor.car", "100", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(domain=DOMAIN, data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        entered, release = asyncio.Event(), asyncio.Event()
        rounds = 0

        async def cycle():
            nonlocal rounds
            rounds += 1
            entered.set()
            await release.wait()
            return SyncOutcome("partial", "routing_incomplete")

        runtime.manual_sync.cycle = cycle
        worker = runtime.manual_sync.trigger()
        await entered.wait()
        action = asyncio.create_task(
            hass.services.async_call(
                DOMAIN, "sync_now", {"entry_id": entry.entry_id}, blocking=True
            )
        )
        await asyncio.sleep(0)
        assert not action.done()
        release.set()
        with pytest.raises(HomeAssistantError, match="partial"):
            await action
        assert worker is runtime.manual_sync.task and rounds == 2

        async def failed():
            raise ValueError("PRIVATE address coordinates")

        runtime.manual_sync.cycle = failed
        with pytest.raises(HomeAssistantError, match="sync_failed") as error:
            await hass.services.async_call(
                DOMAIN, "sync_now", {"entry_id": entry.entry_id}, blocking=True
            )
        assert "PRIVATE" not in str(error.value)
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "value,expected", [("unavailable", "source_unavailable"), ("100", "learning")]
)
async def test_source_not_hidden_by_calendar(hass, value, expected):
    hass.states.async_set("sensor.car", value, {"unit_of_measurement": "km"})
    entry = MockConfigEntry(domain=DOMAIN, data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        runtime.plans = {runtime.data.generated_at.date(): Plan(100, True)}
        await runtime.async_refresh()
        assert runtime.data.status.value == expected
        assert runtime.data.values["today"] is None  # routing disabled
        runtime.source_incompatible = True
        await runtime.async_refresh()
        assert runtime.data.status.value == "source_incompatible"
        assert all(v is None for v in runtime.data.values.values())
        await hass.config_entries.async_unload(entry.entry_id)
