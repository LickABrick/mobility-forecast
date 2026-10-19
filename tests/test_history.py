from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.history import daily_distances, merge_readings
from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.odometer import InvalidReading, kilometers

START = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("value", ["unknown", "unavailable", "nan", "inf", -1, None])
def test_invalid(value):
    with pytest.raises(InvalidReading):
        kilometers(value, "km")


def test_miles():
    assert kilometers(1, "mi") == pytest.approx(1.609344)


def test_merge_and_spikes():
    first = Reading(START, 100)
    next_day = Reading(START + timedelta(days=1), 1600)
    spike = Reading(START + timedelta(days=1, minutes=1), 99000)
    decrease = Reading(START + timedelta(days=2), 10)
    merged, rejected = merge_readings([first], [next_day, spike, decrease, first])
    assert merged == [first, next_day]
    assert rejected == 2
    assert merge_readings(merged, [first, next_day])[0] == merged


def test_gap_allocation():
    readings = [Reading(START, 100), Reading(START + timedelta(days=4), 260)]
    days = daily_distances(readings, ZoneInfo("UTC"))
    assert [d.km for d in days[:4]] == [40] * 4
    assert all(d.quality == "estimated" for d in days[:4])
    assert days[-1].km is None


def test_fresh_zero():
    days = daily_distances(
        [Reading(START, 10), Reading(START + timedelta(days=1), 10)], ZoneInfo("UTC")
    )
    assert days[0].km == 0
    assert days[0].quality == "observed"


def test_late_reading():
    first = Reading(START, 100)
    middle = Reading(START + timedelta(hours=12), 120)
    last = Reading(START + timedelta(days=1), 140)
    assert merge_readings([first, last], [middle])[0] == [first, middle, last]
