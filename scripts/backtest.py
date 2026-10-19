"""Deterministic rolling-origin comparison; run with .venv314/bin/python -m scripts.backtest."""

from datetime import UTC, datetime, timedelta
from statistics import mean, median
from unittest.mock import patch

from custom_components.mobility_forecast.forecasting import predict
from custom_components.mobility_forecast.models import DailyDistance


def old_mean(values):
    center = median(values)
    spread = median(abs(v - center) for v in values)
    cap = center + max(3 * spread, center * 0.5, 5)
    return mean(min(v, cap) for v in values)


def run():
    start = datetime(2025, 1, 6, tzinfo=UTC)
    profiles = {
        "weekend": [0] * 5 + [150] * 2,
        "weekly": [0] * 6 + [250],
        "daily": [40] * 7,
        "commuter": [50] * 5 + [5] * 2,
        "variable": [0, 20, 0, 100, 0, 80, 200],
        "low": [0] * 6 + [15],
    }
    print(
        "profile,expected_week,old_week,new_week,old_7_MAE,new_7_MAE,old_30_MAE,new_30_MAE,old_bias,new_bias,old_aggregate_7_error,new_aggregate_7_error,old_aggregate_30_error,new_aggregate_30_error"
    )
    for name, week in profiles.items():
        values = week * 40
        rows = []
        for estimator in (old_mean, None):
            errors = {7: [], 30: []}
            for cutoff in range(84, 240, 7):
                history = [
                    DailyDistance(
                        (start + timedelta(days=i)).date(), value, "observed", 1
                    )
                    for i, value in enumerate(values[:cutoff])
                ]
                if estimator:
                    with patch(
                        "custom_components.mobility_forecast.forecasting.robust_mean",
                        estimator,
                    ):
                        forecast = predict(history, start + timedelta(days=cutoff))
                else:
                    forecast = predict(history, start + timedelta(days=cutoff))
                for horizon in errors:
                    errors[horizon].append(
                        forecast.values[f"next_{horizon}_days"]
                        - sum(values[cutoff : cutoff + horizon])
                    )
            rows.append(
                (
                    forecast.values["next_7_days"],
                    mean(abs(e) for e in errors[7]),
                    mean(abs(e) for e in errors[30]),
                    mean(errors[7] + errors[30]),
                    sum(errors[7]),
                    sum(errors[30]),
                )
            )
        print(
            name,
            sum(week),
            *(round(v, 2) for pair in zip(*rows) for v in pair),
            sep=",",
        )


if __name__ == "__main__":
    run()
