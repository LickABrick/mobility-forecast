import asyncio
from datetime import UTC, datetime, timedelta
from time import perf_counter
from unittest.mock import patch

import pytest
from homeassistant.core import SupportsResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import Appointment
from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.locations import normalize


def appointments(count, repeated=False):
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    per_day = count // 30
    return [
        Appointment(
            start + timedelta(days=i // per_day, hours=7 + i % per_day),
            start + timedelta(days=i // per_day, hours=7 + i % per_day, minutes=30),
            normalize(f"{52 if repeated else 10 + i / 1000},5"),
            False,
            str(i),
        )
        for i in range(count)
    ]


@pytest.mark.parametrize("count", [150, 300])
@pytest.mark.parametrize("repeated", [False, True])
async def test_large_calendar_continues_bounded(hass, count, repeated, record_property):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    active = peak = calls = 0

    async def routes(call):
        nonlocal active, peak, calls
        active += 1
        peak = max(peak, active)
        calls += 1
        try:
            await asyncio.sleep(0.001)
            return {"routes": [{"distance": 10, "duration": 0}]}
        finally:
            active -= 1

    hass.services.async_register(
        "waze_travel_time",
        "get_travel_times",
        routes,
        supports_response=SupportsResponse.ONLY,
    )
    events = appointments(count, repeated)
    began = perf_counter()
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        return_value=events,
    ) as fetch:
        runtime._schedule_calendar(datetime.now(UTC))
        await runtime.calendar_task
        first_calls = calls
        assert first_calls <= 60 and peak <= 3
        if not repeated:
            assert 0 < len(runtime.plans) < 30
            assert min(runtime.plans) == events[0].start.date()
            assert runtime.calendar_status == "partial"
            assert runtime.calendar_pending_days
        for _ in range(10):
            if not runtime.calendar_pending_days:
                break
            runtime.calendar_next_work = datetime.now(UTC) - timedelta(seconds=1)
            runtime._schedule_calendar(datetime.now(UTC))
            await runtime.calendar_task
        assert runtime.calendar_status == "ready"
        assert len(runtime.plans) == 30
        assert fetch.call_count == 1
        assert all(plan.complete for plan in runtime.plans.values())
        expected_calls = 2 if repeated else count + 30
        assert calls == expected_calls
    elapsed = perf_counter() - began
    record_property("elapsed_seconds", elapsed)
    record_property("waze_calls", calls)
    print(
        f"calendar={count} repeated={repeated} calls={calls} first_cycle={first_calls} peak={peak} elapsed={elapsed:.4f}s"
    )
    await runtime.shutdown()


async def test_deadline_keeps_completed_and_resumes(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    events = appointments(150)

    async def routes(call):
        # Later days block; first three days finish and must remain published.
        if 10.015 <= float(call.data["destination"].split(",")[0]) < 11:
            await asyncio.Event().wait()
        return {"routes": [{"distance": 10, "duration": 0}]}

    hass.services.async_register(
        "waze_travel_time",
        "get_travel_times",
        routes,
        supports_response=SupportsResponse.ONLY,
    )
    with (
        patch(
            "custom_components.mobility_forecast.calendar_manager.fetch_events",
            return_value=events,
        ),
        patch(
            "custom_components.mobility_forecast.coordinator.CALENDAR_REFRESH_BUDGET",
            0.1,
        ),
    ):
        runtime._schedule_calendar(datetime.now(UTC))
        await runtime.calendar_task
        assert len(runtime.plans) == 3
        assert runtime.calendar_status == "partial"
        assert runtime.calendar_metrics["last_failure"] == "refresh_timeout"
        assert len(runtime.calendar_pending_days) == 27
        assert all(p.complete for p in runtime.plans.values())
    await runtime.shutdown()


@pytest.mark.parametrize("count", [150, 300])
async def test_large_nested_calendars(hass, count):
    from dataclasses import replace

    events = appointments(count)
    # One physical parent per day, with the remaining entries nested tickets.
    parents = {}
    for event in events:
        day = event.start.date()
        parents.setdefault(day, replace(event, end=event.start.replace(hour=20)))
    events = [
        parents[event.start.date()]
        if event.identifier == parents[event.start.date()].identifier
        else event
        for event in events
    ]
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={
            "calendars": ["calendar.car"],
            "routing": True,
            "region": "eu",
            "ignore_nested_appointments": True,
        },
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    calls = 0

    async def routes(call):
        nonlocal calls
        calls += 1
        return {"routes": [{"distance": 10, "duration": 0}]}

    hass.services.async_register(
        "waze_travel_time",
        "get_travel_times",
        routes,
        supports_response=SupportsResponse.ONLY,
    )
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        return_value=events,
    ):
        runtime._schedule_calendar(datetime.now(UTC))
        await runtime.calendar_task
        assert runtime.calendar_metrics["nested_ignored"] == count - 30
        assert len(runtime.plans) == 30
        assert runtime.calendar_status == "ready"
        assert calls == 60
    await runtime.shutdown()
