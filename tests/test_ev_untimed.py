from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.ev.models import (
    ChargingOpportunity,
    EVConfig,
    VehicleTelemetry,
)
from custom_components.mobility_forecast.ev.scheduling import recommend


def test_unknown_departure_cannot_be_protected_by_evening_charge():
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    window = ChargingOpportunity(
        "home", now + timedelta(hours=6), now + timedelta(hours=10), 11, 39.6
    )
    result, _, shortfall = recommend(
        EVConfig(60, 20, 11),
        VehicleTelemetry(40, now, "fresh"),
        [],
        [window],
        now,
        True,
        120,
    )
    assert result.status == "insufficient_data"
    assert result.reason == "untimed_demand_reserve_risk"
    assert result.start is None and result.deadline is None and shortfall is None


def test_adequate_energy_accounts_for_untimed_demand():
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    result, _, _ = recommend(
        EVConfig(60, 20, 11), VehicleTelemetry(80, now, "fresh"), [], [], now, True, 30
    )
    assert result.status == "no_charge_needed" and result.confidence == "estimated"
