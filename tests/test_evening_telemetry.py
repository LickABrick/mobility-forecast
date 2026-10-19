from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.history import daily_distances
from custom_components.mobility_forecast.models import Reading


@pytest.mark.parametrize("timezone", ["UTC", "Europe/Amsterdam", "America/New_York"])
@pytest.mark.parametrize("hour", [0, 18])
def test_daily_reporting_weekday_evidence(timezone, hour):
    zone = ZoneInfo(timezone)
    start = datetime(2026, 1, 5, hour, tzinfo=zone)
    readings = []
    km = 1000
    for i in range(113):
        stamp = start + timedelta(days=i)
        if i:
            driving_day = stamp.date() if hour else (stamp - timedelta(days=1)).date()
            km += 50 if driving_day.weekday() < 5 else 0
        readings.append(Reading(stamp, km))
    history = daily_distances(readings, zone)
    result = predict(history, start + timedelta(days=113))
    weekday = [d.baseline_km for d in result.days[:7] if d.day.weekday() < 5]
    weekend = [d.baseline_km for d in result.days[:7] if d.day.weekday() >= 5]
    assert min(weekday) > max(weekend) + 20
    assert result.values["next_7_days"] == pytest.approx(250, rel=0.15)
    if hour:
        assert all(d.quality != "observed" for d in history)
        assert result.quality == "estimated"


def test_five_day_intervals_no_cadence_evidence():
    start = datetime(2026, 1, 1, 18, tzinfo=ZoneInfo("UTC"))
    history = daily_distances(
        [Reading(start + timedelta(days=5 * i), 1000 + 200 * i) for i in range(20)],
        ZoneInfo("UTC"),
    )
    assert all(d.weekday_weight == 0 for d in history)
