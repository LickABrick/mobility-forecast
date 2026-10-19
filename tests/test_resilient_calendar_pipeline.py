from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.models import Reading


@pytest.mark.parametrize("count", [0, 1, 30, 150, 300])
async def test_calendar_service_to_five_sensors(hass, count):
    await hass.config.async_set_time_zone("UTC")
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    source = "sensor.odometer"
    readings = [
        Reading(now - timedelta(days=60 - i), 1000 + 40 * i, "live", source)
        for i in range(61)
    ]
    hass.states.async_set(source, str(readings[-1].km), {"unit_of_measurement": "km"})
    rows = []
    for i in range(count):
        day = i // 5
        hour, location = [
            (8, "52,5"),
            (9, None),
            (10, "53,6"),
            (11, "online"),
            (18, "54,7"),
        ][i % 5]
        start = now + timedelta(days=day % 30, hours=hour)
        end = start + timedelta(hours=4 if i % 5 == 0 else 1)
        row = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "location": location,
            "summary": "PRIVATE TITLE",
        }
        if i % 5 == 4:
            row["start"] = "INVALID PRIVATE"
        rows.append(row)

    async def calendar(call):
        return {"calendar.car": {"events": rows}}

    calls = 0

    async def waze(call):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("PRIVATE ADDRESS")
        return {"routes": [{"distance": 30, "duration": 10}]}

    hass.services.async_register(
        "calendar", "get_events", calendar, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        "waze_travel_time",
        "get_travel_times",
        waze,
        supports_response=SupportsResponse.ONLY,
    )
    entry = MockConfigEntry(
        domain="mobility_forecast",
        title="Car",
        data={"odometer": source},
        options={
            "calendars": ["calendar.car"],
            "routing": True,
            "region": "eu",
            "ignore_nested_appointments": True,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=readings,
    ):
        assert await async_setup_component(hass, "mobility_forecast", {})
        runtime = entry.runtime_data
        if runtime.initialization_task:
            await runtime.initialization_task
        await runtime.import_task
        await runtime.calendar_task
        if runtime.calendar_pending_days:
            retry_now = datetime.now(UTC)
            runtime.calendar_next_work = retry_now - timedelta(seconds=1)
            runtime.calendar_retry_at = {
                day: retry_now - timedelta(seconds=1)
                for day in runtime.calendar_pending_days
            }
            runtime._schedule_calendar(retry_now)
            await runtime.calendar_task
        # Final direct refresh also flushes the coordinator's native debounce.
        await runtime.async_refresh()
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        assert len(entities) == 5
        assert all(
            hass.states.get(entity.entity_id).state not in ("unknown", "unavailable")
            for entity in entities
        )
        assert runtime.calendar_status == "ready"
        assert runtime.calendar_metrics["last_failure"] is None
        assert runtime.calendar_metrics["events_count"] == count
        assert runtime.calendar_metrics["events_invalid_skipped"] == count // 5
        assert runtime.calendar_metrics["events_without_location"] <= (count + 4) // 5
        assert runtime.calendar_metrics["events_virtual_skipped"] <= (count + 4) // 5
        if count >= 30:
            assert runtime.calendar_metrics["events_without_location"] > 0
            assert runtime.calendar_metrics["nested_ignored"] > 0
        assert calls <= 3
        assert runtime.data.values["annual"] == pytest.approx(40 * 365)
        identities = {e.unique_id: e.entity_id for e in entities}
        cache = dict(runtime.store.payload["routes"])
        assert await hass.config_entries.async_reload(entry.entry_id)
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        await entry.runtime_data.calendar_task
        await hass.async_block_till_done()
        assert identities == {
            e.unique_id: e.entity_id
            for e in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        }
        assert entry.runtime_data.store.payload["routes"] == cache
        await hass.config_entries.async_unload(entry.entry_id)
