"""Preliminary mileage is verified planned distance, never an invented baseline."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.comparison import capture
from custom_components.mobility_forecast.ev.demand import reconcile
from custom_components.mobility_forecast.ev.response import horizon_response
from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.models import DailyDistance, Status
from custom_components.mobility_forecast.routing import Plan
from custom_components.mobility_forecast.services import forecast_data


@pytest.mark.parametrize(
    "stamp", ["2026-03-29T00:00:00", "2026-10-25T00:00:00", "2026-10-25T23:55:00"]
)
@pytest.mark.parametrize("count", [0, 3, 6, 7, 60])
def test_preliminary_and_mature(count, stamp):
    now = datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo("Europe/Amsterdam"))
    history = [
        DailyDistance(now.date() - timedelta(days=i + 1), 20, "observed", 1)
        for i in range(count)
    ]
    plans = {
        now.date(): Plan(50, True),
        now.date() + timedelta(days=1): Plan(0, True),
        now.date() + timedelta(days=30): Plan(60, True),
    }
    result = predict(history, now, plans, verified_plans=plans)
    if count >= 7:
        assert result == predict(history, now, plans)
        assert result.values["next_7_days"] is not None
        return
    assert result.status == Status.CALENDAR_ONLY
    assert result.quality == "calendar_only"
    assert result.values == {
        "today": 50,
        "tomorrow": 0,
        "next_7_days": None,
        "next_30_days": None,
        "annual": None,
    }
    assert result.days[2].total_km is None
    assert result.days[30].total_km == 60
    assert all(
        day.baseline_km is None and day.low_km is None and day.high_km is None
        for day in result.days
    )
    assert not capture({}, result, now.replace(hour=23, minute=55))
    assert reconcile(result.days, plans, [], now) == ([], [])
    response = horizon_response({}, 7, now, result.days, 20)
    assert response["energy_demand_kwh"] is None
    runtime = SimpleNamespace(
        data=result,
        entry=SimpleNamespace(entry_id="car"),
        hass=SimpleNamespace(config=SimpleNamespace(time_zone="Europe/Amsterdam")),
    )
    rows = forecast_data(runtime)["forecast"]
    assert rows[0]["data_quality"] == "calendar_only"
    assert rows[2]["predicted_km"] is None
    assert rows[2]["data_quality"] == "unknown"


@pytest.mark.parametrize(
    "plan", [None, Plan(10, False), Plan(-1, True), Plan(float("nan"), True)]
)
def test_no_qualifying_plan(plan):
    now = datetime(2026, 10, 20, tzinfo=ZoneInfo("Europe/Amsterdam"))
    plans = {now.date(): plan} if plan else {}
    result = predict([], now, plans, verified_plans=plans)
    assert result.status == Status.LEARNING
    assert all(value is None for value in result.values.values())
    assert all(day.total_km is None for day in result.days)


def test_unverified_plan_never_qualifies():
    now = datetime(2026, 10, 20, tzinfo=ZoneInfo("Europe/Amsterdam"))
    result = predict([], now, {now.date(): Plan(100, True)})
    assert result.status == Status.LEARNING
    assert result.values["today"] is None
