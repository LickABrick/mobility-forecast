"""Native HA entity lifecycle, diagnostic identity and safe timeline migration."""

import asyncio
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN
from custom_components.mobility_forecast.routing import Plan
from custom_components.mobility_forecast.status_sensor import KEYS


@pytest.mark.parametrize(
    "disabled", [er.RegistryEntryDisabler.INTEGRATION, er.RegistryEntryDisabler.USER]
)
async def test_entities_sync_reload_and_timeline(hass, disabled):
    hass.states.async_set("sensor.car", "1000", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(domain=DOMAIN, title="Car", data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    timeline = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_mileage_timeline",
        config_entry=entry,
        disabled_by=disabled,
    )
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        await hass.async_block_till_done()

        def entity(key):
            return registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}"
            )

        for key in KEYS:
            row = registry.async_get(entity(key))
            assert row.disabled_by is None
            assert row.entity_category == EntityCategory.DIAGNOSTIC
            assert row.device_id == registry.async_get(entity("today")).device_id
        assert hass.states.get(entity("forecast_status")).state == "learning"
        assert hass.states.get(entity("calendar_status")).state == "disabled"
        assert hass.states.get(entity("last_successful_sync")).state == "unknown"
        assert (
            hass.states.get(entity("last_successful_sync")).attributes["device_class"]
            == "timestamp"
        )
        assert (registry.async_get(timeline.entity_id).disabled_by is None) == (
            disabled == er.RegistryEntryDisabler.INTEGRATION
        )
        entered, release = asyncio.Event(), asyncio.Event()
        original = runtime.manual_sync.cycle

        async def slow():
            runtime.manual_sync.set_phase("calendar")
            entered.set()
            await release.wait()

        runtime.manual_sync.cycle = slow
        switch_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{entry.entry_id}_manual_sync"
        )
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch_id}, blocking=True
        )
        await entered.wait()
        assert hass.states.get(switch_id).state == "on"
        assert hass.states.get(entity("sync_status")).state == "syncing"
        assert hass.states.get(entity("sync_status")).attributes["phase"] == "calendar"
        release.set()
        await runtime.manual_sync.task
        await hass.async_block_till_done()
        success = runtime.manual_sync.successful_at
        assert success.tzinfo is not None
        assert hass.states.get(switch_id).state == "off"
        assert (
            hass.states.get(entity("sync_status")).attributes["last_result"]
            == "success"
        )
        runtime.manual_sync.cycle = original
        assert await hass.config_entries.async_reload(entry.entry_id)
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        assert entry.runtime_data.manual_sync.successful_at == success
        assert not entry.runtime_data.manual_sync.running
        assert runtime.manual_sync.listeners == []
        reloaded = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert reloaded.manual_sync.listeners == []


@pytest.mark.parametrize(
    "age,status,eligible",
    [
        (0, "ready", True),
        (3, "provisional", False),
        (0, "stale", False),
        (0, "partial", True),
    ],
)
async def test_runtime_verified_calendar_gate(hass, age, status, eligible):
    hass.states.async_set("sensor.car", "100", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Car",
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
        now = dt_util.utcnow().astimezone(ZoneInfo(hass.config.time_zone))
        runtime.plans = {now.date(): Plan(40, True)}
        runtime.day_verified = {now.date(): now - timedelta(hours=age)}
        runtime.calendar_status = status
        runtime.calendar_refreshed_at = now
        await runtime.async_refresh()
        assert (runtime.data.values["today"] == 40) == eligible
        assert runtime.data.status.value == (
            "calendar_only" if eligible else "learning"
        )
        if eligible:
            # A retained numeric plan is not verified for an edited appointment.
            runtime.candidate_fingerprints[now.date()] = "changed"
            runtime.day_fingerprints[now.date()] = "old"
            await runtime.async_refresh()
            assert runtime.data.values["today"] is None
            runtime.candidate_fingerprints[now.date()] = "old"
            await runtime.async_refresh()
            assert runtime.data.values["today"] == 40
            runtime.plans.clear()  # authoritative cancellation
            await runtime.async_refresh()
            assert runtime.data.values["today"] is None
        await hass.config_entries.async_unload(entry.entry_id)
