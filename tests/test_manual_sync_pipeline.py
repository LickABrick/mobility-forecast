"""Real HA entry pipeline, with only provider/history boundaries replaced."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_action_forces_calendar_and_ingests_odometer(hass):
    hass.states.async_set("sensor.car", "10000", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Car",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
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
        ) as fetch,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        await runtime.calendar_task
        calls = fetch.call_count
        hass.states.async_set("sensor.car", "10001", {"unit_of_measurement": "km"})
        await hass.services.async_call(
            DOMAIN, "sync_now", {"entry_id": entry.entry_id}, blocking=True
        )
        assert fetch.call_count == calls + 1
        assert runtime.readings[-1].km == 10001
        assert runtime.manual_sync.status == "success"
        assert not runtime.manual_sync.running
        # Failure is a sanitized result, not a stuck toggle or leaked exception.
        with patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            side_effect=RuntimeError("PRIVATE"),
        ):
            await runtime.manual_sync.request()
        assert runtime.manual_sync.status == "error"
        assert runtime.manual_sync.error == "sync_failed"
        await hass.config_entries.async_unload(entry.entry_id)


async def test_invalid_action_entry(hass):
    from custom_components.mobility_forecast.services import register_services

    register_services(hass)
    with pytest.raises(HomeAssistantError, match="Vehicle is not loaded"):
        await hass.services.async_call(
            DOMAIN, "sync_now", {"entry_id": "missing"}, blocking=True
        )


async def test_manual_pipeline_refreshes_ev(hass):
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
        from types import SimpleNamespace

        # Check orchestration independently of vehicle entity and network parsing.
        ev = SimpleNamespace(
            pending=None,
            task=None,
            schedule=lambda: None,
            launch=lambda: None,
            close=AsyncMock(),
            result={},
        )
        runtime.ev = ev

        def launch():
            ev.task = hass.async_create_task(ev_update())

        ev_update = AsyncMock()
        ev.launch = launch
        await runtime.manual_sync.request()
        ev_update.assert_awaited_once()
        await hass.config_entries.async_unload(entry.entry_id)
