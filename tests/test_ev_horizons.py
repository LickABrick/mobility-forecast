from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.ev.response import horizon_response
from custom_components.mobility_forecast.models import DailyForecast


@pytest.mark.parametrize("days", [1, 2, 3, 7])
def test_horizon_consistent_and_nonmutating(days):
    now = datetime(2026, 10, 25, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    later = now + timedelta(days=6)
    source = {
        "status": "ready",
        "recommendation": {
            "start": later.isoformat(),
            "end": (later + timedelta(hours=2)).isoformat(),
        },
        "alternative": None,
        "shortfall_at": later.isoformat(),
        "unallocated_demand": [
            {"date": (now + timedelta(days=i)).date().isoformat(), "distance_km": 10}
            for i in range(7)
        ],
        "opportunities": [
            {
                "start": later.isoformat(),
                "end": (later + timedelta(hours=2)).isoformat(),
            }
        ],
    }
    original = deepcopy(source)
    forecasts = [
        DailyForecast((now + timedelta(days=i)).date(), 10, 10, 5, 15) for i in range(7)
    ]
    result = horizon_response(source, days, now, forecasts, 20)
    assert result["energy_demand_kwh"] == days * 2
    assert len(result["unallocated_demand"]) == days
    if days < 7:
        assert result["shortfall_at"] is None and result["recommendation"] is None
        assert result["status"] == "insufficient_data"
    assert source == original
