from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.history import (
    compact_readings,
    daily_distances,
    merge_readings,
)
from custom_components.mobility_forecast.models import Reading


@pytest.mark.parametrize("seconds", [10, 60, 3600, 86400 * 3])
def test_frequency_independent_retention(seconds):
    start = datetime(2025, 1, 1, tzinfo=UTC)
    values = [
        Reading(start + timedelta(seconds=i), 100 + i / 86400 * 40)
        for i in range(0, 86400 * 8 + 1, seconds)
    ]
    compact = compact_readings(values)
    assert len(compact) <= 8 * 48 + 1
    assert compact[-1] == values[-1]
    before = daily_distances(values, ZoneInfo("UTC"))
    after = daily_distances(compact, ZoneInfo("UTC"))
    assert [d.quality for d in before] == [d.quality for d in after]
    assert [d.coverage for d in before] == pytest.approx([d.coverage for d in after])
    assert [d.km for d in before] == pytest.approx([d.km for d in after])
    assert compact_readings(compact) == compact


def test_three_years_not_truncated_by_latest_n():
    start = datetime(2023, 1, 1, tzinfo=UTC)
    values = [
        Reading(start + timedelta(hours=i), 100 + i) for i in range(1095 * 24 + 1)
    ]
    result, _ = merge_readings([], values)
    assert result[0] == values[0]
    assert result[-1] == values[-1]
    assert len(result) == len(values)
