from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.core import State

from custom_components.mobility_forecast.history import import_history, merge_readings
from custom_components.mobility_forecast.models import Reading


@pytest.mark.parametrize("days,expected", [(0, 0), (10, 40), (30, 120)])
async def test_queries_skip_unretained_years(hass, days, expected):
    now = datetime(2026, 10, 1, tzinfo=UTC)
    source = "sensor.odometer"
    hass.config.components.add("recorder")

    async def executor(job):
        return job()

    oldest = State(
        source,
        "100",
        {"unit_of_measurement": "km"},
        last_updated=now - timedelta(days=days),
    )
    with (
        patch(
            "homeassistant.components.recorder.get_instance",
            return_value=SimpleNamespace(async_add_executor_job=executor),
        ),
        patch(
            "homeassistant.components.recorder.statistics.get_metadata", return_value={}
        ),
        patch(
            "homeassistant.components.recorder.history.state_changes_during_period",
            return_value={source: [oldest]} if days else {},
        ) as boundary,
        patch(
            "homeassistant.components.recorder.history.get_significant_states",
            return_value={},
        ) as raw,
    ):
        await import_history(hass, source, now)
        assert boundary.call_count == 1
        assert raw.call_count == expected


def test_statistics_inside_raw_gap_not_dropped():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    raw = [
        Reading(start, 100, "recorder"),
        Reading(start + timedelta(days=5), 200, "recorder"),
    ]
    stats = [
        Reading(start + timedelta(days=i), 100 + 20 * i, "statistics")
        for i in range(1, 5)
    ]
    merged, rejected = merge_readings(raw, stats)
    assert len(merged) == 6 and rejected == 0
    assert merged[-1].km - merged[0].km == 100
    assert merge_readings(merged, stats)[0] == merged
