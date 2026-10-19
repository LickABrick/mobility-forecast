from datetime import UTC, datetime, timedelta

import pytest

from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.models import DailyDistance
from custom_components.mobility_forecast.routing import Plan


@pytest.mark.parametrize(
    "baseline,route,expected", [(45, 110, 110), (80, 30, 80), (40, None, 40)]
)
def test_conservative_overlay(baseline, route, expected):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    days = [
        DailyDistance((now - timedelta(days=i)).date(), baseline, "observed", 1)
        for i in range(60, 0, -1)
    ]
    plans = {now.date(): Plan(route, True)} if route is not None else {}
    forecast = predict(days, now, plans)
    assert forecast.values["today"] == expected
    assert forecast.values["annual"] == baseline * 365
    assert forecast.values["next_7_days"] == expected + baseline * 6
