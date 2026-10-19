from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.history import daily_distances, merge_readings
from custom_components.mobility_forecast.models import DailyDistance, Reading


async def test_first_import_not_truncated_by_current_reading(hass):
    hass.states.async_set("sensor.odometer", "100", {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain="mobility_forecast", data={"odometer": "sensor.odometer"}
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ) as importer:
        await runtime.initialize()
        await hass.async_block_till_done()
        assert importer.call_args.args[3] is None
        await entry._async_process_on_unload(hass)
        await runtime.shutdown()


def test_raw_overlap_removes_artificial_statistics_steps():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    readings, _ = merge_readings(
        [],
        [
            Reading(start, 100, "recorder"),
            Reading(start + timedelta(hours=2), 140, "recorder"),
            Reading(start + timedelta(hours=1), 135, "statistics"),
        ],
    )
    assert len(readings) == 2


def test_statistics_never_create_precise_weekdays():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    readings = [
        Reading(start + timedelta(hours=i), 100 + i, "statistics")
        for i in range(24 * 40)
    ]
    days = daily_distances(readings, ZoneInfo("UTC"))
    assert all(d.quality != "observed" for d in days)
    assert predict(days, start + timedelta(days=41)).quality == "estimated"


@pytest.mark.parametrize("day", ["2026-03-29", "2026-10-25"])
def test_dst_interval_conserves_kilometers(day):
    zone = ZoneInfo("Europe/Amsterdam")
    start = datetime.fromisoformat(day).replace(tzinfo=zone)
    end = start + timedelta(days=1)
    days = daily_distances([Reading(start, 100), Reading(end, 140)], zone)
    assert days[0].km == pytest.approx(40)
    assert days[0].coverage == pytest.approx(1)


def test_already_driven_not_predicted_again_in_rolling_period():
    now = datetime(2026, 1, 30, 12, tzinfo=UTC)
    days = [
        DailyDistance((now - timedelta(days=i)).date(), 40, "observed", 1)
        for i in range(28, 0, -1)
    ]
    days.append(DailyDistance(now.date(), 100, "partial", 0.5, 100))
    result = predict(days, now)
    assert result.values["today"] == 100
    assert result.values["next_7_days"] == 260
