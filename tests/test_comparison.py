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


def test_metrics_only_complete_observed_pre_day_predictions():
    from custom_components.mobility_forecast.comparison import comparisons, metrics

    now = datetime(2026, 1, 5, tzinfo=ZoneInfo("UTC"))
    snapshots = {
        "2026-01-02": {
            "valid": True,
            "predicted_km": 42,
            "captured_at": "2026-01-01T23:55:00+00:00",
        },
        "2026-01-03": {"valid": True, "predicted_km": 55},
        "2026-01-04": {"valid": True, "predicted_km": 35},
    }
    history = [
        DailyDistance(now.date() - timedelta(days=3), 48, "observed", 1),
        DailyDistance(now.date() - timedelta(days=2), 51, "observed", 1),
        DailyDistance(now.date() - timedelta(days=1), 28, "estimated", 1),
        DailyDistance(now.date(), 100, "observed", 1),
    ]
    rows = comparisons(snapshots, history, now, 4)
    result = metrics(rows, 4)
    assert result["evaluated_days"] == 2
    assert result["mae_km"] == 5
    assert result["bias_km"] == 1
    assert result["predicted_km"] == 97 and result["actual_km"] == 99
    assert result["missing_predictions"] == 1
    assert rows[-1]["actual_quality"] == "estimated" and not rows[-1]["eligible"]
    assert rows[0]["actual_km"] is None
    assert rows[-1]["difference_km"] == -7
