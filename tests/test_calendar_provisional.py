from datetime import UTC, datetime, timedelta

import pytest

from custom_components.mobility_forecast.calendar_storage import restore


@pytest.mark.parametrize(
    "hours,retained",
    [
        (5 / 60, True),
        (1.5, True),
        (3, True),
        (8, True),
        (24, True),
        (24.01, False),
        (48, False),
    ],
)
def test_bounded_provisional_retention(hours, retained):
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    stamp = (now - timedelta(hours=hours)).isoformat()
    row = {
        "schema": 1,
        "complete": True,
        "routing_identity": "identity",
        "fingerprint": "a" * 64,
        "distance_km": 95,
        "verified_at": stamp,
        "routed_at": stamp,
    }
    result = restore({"2026-10-21": row}, "identity", now)
    assert bool(result) == retained
    if retained:
        assert result[now.date() + timedelta(days=1)][0].distance_km == 95
    assert restore({"2026-10-21": row}, "changed", now) == {}
