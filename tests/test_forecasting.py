from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.models import DailyDistance, Status

NOW = datetime(2026, 2, 2, tzinfo=UTC)


def history(values, quality="observed"):
    return [
        DailyDistance((NOW - timedelta(days=len(values) - i)).date(), v, quality, 1)
        for i, v in enumerate(values)
    ]


def test_stable():
    forecast = predict(history([40] * 80), NOW)
    assert forecast.values == {
        "today": 40,
        "tomorrow": 40,
        "next_7_days": 280,
        "next_30_days": 1200,
        "annual": 14600,
    }
    assert forecast.status == Status.READY


def test_insufficient_and_parked():
    assert predict(history([40] * 2), NOW).values["today"] is None
    assert predict(history([0] * 30), NOW).values["today"] == 0


def test_vacation():
    assert predict(history([40] * 59 + [1500]), NOW).values["today"] < 45


def test_adaptation():
    assert predict(history([20] * 56 + [70] * 56), NOW).values["today"] > 50


def test_weekdays():
    days = history([0] * 84)
    days = [
        DailyDistance(d.day, 50 if d.day.weekday() < 5 else 10, "observed", 1)
        for d in days
    ]
    forecast = predict(days, NOW)
    assert forecast.days[0].baseline_km > forecast.days[5].baseline_km + 20


def test_sparse_is_qualified():
    forecast = predict(history([40] * 30, "estimated"), NOW)
    assert forecast.status == Status.PROVISIONAL


def test_variability():
    steady = predict(history([40] * 80), NOW)
    variable = predict(history([0, 80] * 40), NOW)
    assert (
        variable.days[0].high_km - variable.days[0].low_km
        > steady.days[0].high_km - steady.days[0].low_km
    )


@pytest.mark.parametrize("stamp", ["2026-03-29T12:00:00", "2026-10-25T12:00:00"])
def test_dst(stamp):
    now = datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo("Europe/Amsterdam"))
    days = [
        DailyDistance((now - timedelta(days=i)).date(), 40, "observed", 1)
        for i in range(80, 0, -1)
    ]
    assert predict(days, now).values["next_7_days"] == pytest.approx(280)
