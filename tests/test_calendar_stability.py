import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.routing import Plan
from custom_components.mobility_forecast.sensor import ForecastSensor


@pytest.mark.xfail(
    strict=True, reason="Refresh clears active plans before candidate routing completes"
)
async def test_unchanged_calendar_never_publishes_baseline_dip(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        title="Car",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = now + timedelta(days=1)
    runtime.readings = [
        Reading(now - timedelta(days=i), 10000 - i * 35) for i in range(60, -1, -1)
    ]
    hass.states.async_set("sensor.car", "10000", {"unit_of_measurement": "km"})
    runtime.calendar_signature = repr(dict(entry.options))
    runtime.plans = {tomorrow.date(): Plan(67, True)}
    events = [
        Appointment(
            tomorrow + timedelta(hours=9),
            tomorrow + timedelta(hours=10),
            normalize("52,5"),
            False,
            "one",
        )
    ]
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow(*args):
        entered.set()
        await release.wait()
        return {tomorrow.date(): Plan(67, True)}

    sensor = ForecastSensor(runtime, "tomorrow")
    sensor.hass = hass
    sensor.entity_id = "sensor.car_tomorrow"
    runtime.async_set_updated_data(
        await runtime._async_update_data()
    ) if False else None
    # Publish initial state without triggering a sync.
    runtime.calendar_refreshed_at = now
    runtime.async_set_updated_data(await runtime._async_update_data())
    sensor.async_write_ha_state()
    assert hass.states.get(sensor.entity_id).state == "67"
    runtime.calendar_refreshed_at = now - timedelta(hours=1)
    try:
        with (
            patch(
                "custom_components.mobility_forecast.calendar_manager.fetch_events",
                return_value=events,
            ),
            patch(
                "custom_components.mobility_forecast.routing._plan_journeys",
                side_effect=slow,
            ),
        ):
            runtime._schedule_calendar(now)
            await entered.wait()
            runtime.async_set_updated_data(await runtime._async_update_data())
            sensor.async_write_ha_state()
            assert hass.states.get(sensor.entity_id).state == "67"
            release.set()
            await runtime.calendar_task
    finally:
        release.set()
        await runtime.shutdown()
