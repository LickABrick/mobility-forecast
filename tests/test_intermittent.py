from datetime import UTC, datetime, timedelta

import pytest

from custom_components.mobility_forecast.forecasting import predict, robust_mean
from custom_components.mobility_forecast.models import DailyDistance

START = datetime(2025, 1, 6, tzinfo=UTC)


def series(values, quality="observed"):
    return [
        DailyDistance((START + timedelta(days=i)).date(), v, quality, 1)
        for i, v in enumerate(values)
    ]


@pytest.mark.parametrize(
    "week",
    [
        [0] * 5 + [150] * 2,
        [0] * 6 + [250],
        [50] * 5 + [5] * 2,
        [40] * 7,
        [0] * 6 + [15],
        [0, 20, 0, 100, 0, 80, 200],
    ],
)
def test_recurring_usage_preserved(week):
    result = predict(series(week * 12), START + timedelta(weeks=12))
    assert result.values["next_7_days"] == pytest.approx(sum(week), rel=0.12)
    assert result.values["annual"] == pytest.approx(sum(week) * 365 / 7, rel=0.12)
    assert all(d.total_km >= 0 for d in result.days)


def test_sporadic_and_exceptional():
    assert robust_mean(([0] * 13 + [120]) * 6) == pytest.approx(120 / 14)
    assert robust_mean([40] * 83 + [1500]) < 44


def test_frequency_change_and_sparse():
    values = ([0] * 6 + [30]) * 8 + [60] * 56
    assert (
        predict(series(values), START + timedelta(days=len(values))).values[
            "next_7_days"
        ]
        > 350
    )
    sparse = predict(
        series(([0] * 5 + [150] * 2) * 12, "estimated"), START + timedelta(weeks=12)
    )
    assert sparse.quality == "estimated"
    assert max(d.baseline_km for d in sparse.days[:7]) == min(
        d.baseline_km for d in sparse.days[:7]
    )
