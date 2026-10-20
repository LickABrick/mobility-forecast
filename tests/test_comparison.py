from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.comparison import capture, migrate_snapshots
from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.models import DailyDistance


@pytest.mark.parametrize("stamp", ["2026-03-28T23:55:00", "2026-10-24T23:55:00"])
def test_immutable_pre_day_capture(stamp):
    now = datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo("Europe/Amsterdam"))
    history = [
        DailyDistance(now.date() - timedelta(days=i), 40, "observed", 1)
        for i in range(60, 0, -1)
    ]
    forecast = predict(history, now)
    snapshots = {}
    assert capture(snapshots, forecast, now)
    original = dict(snapshots)
    forecast.days = []
    assert not capture(snapshots, forecast, now + timedelta(days=1))
    assert snapshots == original
    value = next(iter(snapshots.values()))
    assert value["lead_seconds"] == 300
    assert value["valid"]
    legacy = migrate_snapshots({"2026-01-01": 42})
    assert not legacy["2026-01-01"]["valid"]
    assert migrate_snapshots(legacy) == legacy
