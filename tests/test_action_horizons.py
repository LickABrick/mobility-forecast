"""Daily response contract preserves local dates and independent snapshots."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from custom_components.mobility_forecast.services import forecast_data


@pytest.mark.parametrize("days", [1, 7, 30, 31, 365])
@pytest.mark.parametrize("start", [date(2026, 3, 28), date(2026, 10, 24)])
def test_forecast_dates_and_dst(days, start):
    records = [
        SimpleNamespace(
            day=start + timedelta(days=i), total_km=12, low_km=8, high_km=20
        )
        for i in range(365)
    ]
    runtime = SimpleNamespace(
        hass=SimpleNamespace(config=SimpleNamespace(time_zone="Europe/Amsterdam")),
        entry=SimpleNamespace(entry_id="car"),
        data=SimpleNamespace(generated_at=datetime.now(UTC), days=records),
    )
    result = forecast_data(runtime, days)
    assert len(result["forecast"]) == days
    assert result["forecast"][0]["date"] == start.isoformat()
    assert result["forecast"][0]["timestamp"].startswith(f"{start}T00:00:00")
    result["forecast"][0]["predicted_km"] = 999
    assert records[0].total_km == 12
    assert len(forecast_data(runtime, 365)["forecast"]) == 365
