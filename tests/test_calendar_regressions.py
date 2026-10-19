import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import (
    Appointment,
    normalize_events,
    preprocess_appointments,
)
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import (
    Route,
    WazeProvider,
    plan_journeys,
)


async def test_nested_option_persists_and_can_disable(hass):
    entry = MockConfigEntry(domain="mobility_forecast", data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    for enabled in (True, False):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "calendars"}
        )
        field = next(
            key
            for key in flow["data_schema"].schema
            if key.schema == "ignore_nested_appointments"
        )
        assert field.default() == (not enabled if enabled is False else False)
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {"routing": False, "calendars": [], "ignore_nested_appointments": enabled},
        )
        assert result["type"] == "create_entry"
        assert entry.options["ignore_nested_appointments"] is enabled


async def test_inflight_cache_region_failure_and_cancellation():
    began = asyncio.Event()
    release = asyncio.Event()

    async def response(*args, **kwargs):
        began.set()
        await release.wait()
        return {"routes": [{"distance": 10, "duration": 1}]}

    services = SimpleNamespace(
        has_service=Mock(return_value=True), async_call=AsyncMock(side_effect=response)
    )
    cache = {}
    provider = WazeProvider(SimpleNamespace(services=services), "eu", cache)
    a, b = normalize("52,5"), normalize("53,6")
    task = asyncio.create_task(provider.get_route(a, b))
    await began.wait()
    waiter = asyncio.create_task(provider.get_route(a, b))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    assert (await task).distance_km == 10
    assert provider.inflight == {}
    await provider.get_route(a, b)
    assert services.async_call.await_count == 1
    await WazeProvider(SimpleNamespace(services=services), "us", cache).get_route(a, b)
    assert services.async_call.await_count == 2
    services.async_call.side_effect = RuntimeError("PRIVATE ADDRESS")
    assert await provider.get_route(b, a) is None
    assert len(cache) == 2


async def test_nested_calls_disabled_vs_enabled():
    start = datetime(2026, 1, 1, 8, tzinfo=UTC)
    parent = Appointment(
        start, start + timedelta(hours=4), normalize("52,5"), False, "parent"
    )
    child = Appointment(
        start + timedelta(hours=1),
        start + timedelta(hours=2),
        normalize("53,6"),
        False,
        "child",
    )
    for enabled, expected_calls, complete in [(False, 0, False), (True, 2, True)]:
        selected, _ = preprocess_appointments([child, parent], enabled)
        provider = SimpleNamespace(get_route=AsyncMock(return_value=Route(12, 1)))
        plan = (await plan_journeys(selected, normalize("51,4"), provider))[
            start.date()
        ]
        assert plan.complete is complete
        assert provider.get_route.await_count == expected_calls
        assert plan.distance_km == (24 if enabled else 0)


def test_virtual_and_unresolved_do_not_deduplicate():
    row = {"start": "2026-01-01T09:00:00+00:00", "end": "2026-01-01T10:00:00+00:00"}
    events = normalize_events(
        [{**row, "location": "online"}, {**row, "location": "unknown venue"}], UTC
    )
    assert len(events) == 2
    assert len(preprocess_appointments(events)[0]) == 0


async def test_unavailable_provider_and_empty_calendar(hass):
    from custom_components.mobility_forecast.coordinator import VehicleCoordinator

    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"routing": True, "calendars": ["calendar.car"], "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    now = datetime.now(UTC).replace(hour=9)
    events = [
        Appointment(now, now + timedelta(hours=1), normalize("52,5"), False, "one")
    ]
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        return_value=events,
    ):
        runtime._schedule_calendar(now)
        await runtime.calendar_task
        assert runtime.calendar_status == "routing_unavailable"
        assert runtime.calendar_metrics["last_failure"] == "provider_unavailable"
        assert all(
            not p.complete and p.distance_km == 0 for p in runtime.plans.values()
        )
    await runtime.shutdown()
