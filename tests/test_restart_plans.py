"""Real entry unload/reload and reconstructed Store, not reused plan objects."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.routing import Plan


@pytest.mark.parametrize("age_hours", [0, 5 / 60, 3, 8, 24, 25])
async def test_reload_restores_calendar_before_fetch(hass, age_hours, freezer):
    freezer.move_to("2026-10-20T12:00:00+00:00")
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = now + timedelta(days=1)
    readings = [
        Reading(now - timedelta(days=i), 10000 - i * 36) for i in range(60, -1, -1)
    ]
    entry = MockConfigEntry(
        domain="mobility_forecast",
        title="Car",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.car", "10000", {"unit_of_measurement": "km"})
    events = [
        Appointment(
            tomorrow + timedelta(hours=9),
            tomorrow + timedelta(hours=10),
            normalize("52,5"),
            False,
            "private",
        )
    ]
    with (
        patch(
            "custom_components.mobility_forecast.coordinator.import_history",
            return_value=readings,
        ),
        patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            return_value=events,
        ),
        patch(
            "custom_components.mobility_forecast.routing._plan_journeys",
            return_value={tomorrow.date(): Plan(95, True)},
        ),
    ):
        assert await async_setup_component(hass, "mobility_forecast", {})
        old = entry.runtime_data
        await old.initialization_task
        await old.import_task
        await old.calendar_task
        await old.async_refresh()
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", "mobility_forecast", f"{entry.entry_id}_tomorrow"
        )
        await hass.async_block_till_done()
        assert float(hass.states.get(entity_id).state) == 95
        for row in old.store.payload["calendar_plans"].values():
            row["verified_at"] = (
                datetime.now(UTC) - timedelta(hours=age_hours)
            ).isoformat()
            row["routed_at"] = row["verified_at"]
        assert await hass.config_entries.async_unload(entry.entry_id)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed(*args):
        entered.set()
        await release.wait()
        return events

    try:
        with (
            patch(
                "custom_components.mobility_forecast.coordinator.import_history",
                return_value=readings,
            ),
            patch(
                "custom_components.mobility_forecast.calendar_manager.fetch_events",
                side_effect=delayed,
            ),
            patch(
                "custom_components.mobility_forecast.routing._plan_journeys",
                return_value={tomorrow.date(): Plan(95, True)},
            ),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
            runtime = entry.runtime_data
            assert runtime is not old and runtime.store is not old.store
            await runtime.initialization_task
            await entered.wait()
            await hass.async_block_till_done()
            first = float(hass.states.get(entity_id).state)
            if age_hours <= 24:
                assert first == 95
            else:
                # Existing robust baseline includes the partial current-day
                # history bracket; it is approximately, not exactly, 36 km.
                assert 35 < first < 37
            if 2 < age_hours <= 24:
                assert runtime.calendar_status == "provisional"
            # Trigger manual sync while startup verification is blocked.
            runtime.manual_sync.trigger()
            assert runtime.manual_sync.running
            assert float(hass.states.get(entity_id).state) == first
            release.set()
            await runtime.calendar_task
            await runtime.manual_sync.task
            await runtime.async_refresh()
            assert runtime.manual_sync.status == "success"
            assert float(hass.states.get(entity_id).state) == 95
    finally:
        release.set()
        await hass.config_entries.async_unload(entry.entry_id)
