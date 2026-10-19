from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.core import State

from custom_components.mobility_forecast.history import import_history


async def test_recorder_and_physical_statistics(hass):
    now = datetime(2026, 1, 2, tzinfo=UTC)
    start = now - timedelta(days=1)
    hass.config.components.add("recorder")

    async def execute(job):
        return job()

    recorder = SimpleNamespace(async_add_executor_job=execute)
    state = State(
        "sensor.odometer", "200", {"unit_of_measurement": "km"}, last_updated=now
    )
    with (
        patch("homeassistant.components.recorder.get_instance", return_value=recorder),
        patch(
            "homeassistant.components.recorder.statistics.get_metadata",
            return_value={
                "sensor.odometer": (1, {"unit_of_measurement": "km", "has_sum": True})
            },
        ),
        patch(
            "homeassistant.components.recorder.statistics.statistics_during_period",
            return_value={
                "sensor.odometer": [
                    {"start": start.timestamp(), "state": 100, "sum": 999999}
                ]
            },
        ),
        patch(
            "homeassistant.components.recorder.history.state_changes_during_period",
            return_value={
                "sensor.odometer": [
                    State(
                        "sensor.odometer",
                        "100",
                        {"unit_of_measurement": "km"},
                        last_updated=start,
                    )
                ]
            },
        ),
        patch(
            "homeassistant.components.recorder.history.get_significant_states",
            return_value={"sensor.odometer": [state]},
        ),
    ):
        readings = await import_history(hass, "sensor.odometer", now, start)
        assert [r.km for r in readings] == [100, 100, 200]
        assert readings[0].source == "recorder"
        assert readings[1].source == "statistics"


async def test_no_recorder(hass):
    assert await import_history(hass, "sensor.odometer", datetime.now(UTC)) == []
