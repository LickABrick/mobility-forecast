import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.routing import Plan


async def test_unchanged_calendar_never_publishes_baseline_dip(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        title="Car",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = midnight + timedelta(days=1)
    readings = [
        Reading(midnight - timedelta(days=i), 10000 - i * 35) for i in range(60, -1, -1)
    ]
    hass.states.async_set("sensor.car", "10000", {"unit_of_measurement": "km"})
    events = [
        Appointment(
            tomorrow + timedelta(hours=9),
            tomorrow + timedelta(hours=10),
            normalize_location(),
            False,
            "one",
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
            return_value={tomorrow.date(): Plan(67, True)},
        ),
    ):
        assert await async_setup_component(hass, "mobility_forecast", {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        await runtime.calendar_task
        await runtime.async_refresh()
        await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "mobility_forecast", f"{entry.entry_id}_tomorrow"
    )
    assert float(hass.states.get(entity_id).state) == 67
    publications = []
    unsubscribe = hass.bus.async_listen(
        "state_changed",
        lambda event: (
            publications.append(event.data["new_state"])
            if event.data["entity_id"] == entity_id
            else None
        ),
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow(*args):
        entered.set()
        await release.wait()
        return events

    try:
        with patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            side_effect=slow,
        ):
            runtime.calendar_refreshed_at = now - timedelta(hours=1)
            runtime._schedule_calendar(now)
            await entered.wait()
            await runtime.async_refresh()
            await hass.async_block_till_done()
            assert float(hass.states.get(entity_id).state) == 67
            release.set()
            await runtime.calendar_task
            await runtime.async_refresh()
            await hass.async_block_till_done()
            assert float(hass.states.get(entity_id).state) == 67
            assert all(float(state.state) == 67 for state in publications)
            # Status/progress attributes may publish even with identical mileage.
            assert len(publications) == 2
    finally:
        unsubscribe()
        release.set()
        await hass.config_entries.async_unload(entry.entry_id)


def normalize_location():
    from custom_components.mobility_forecast.locations import normalize

    return normalize("52,5")
