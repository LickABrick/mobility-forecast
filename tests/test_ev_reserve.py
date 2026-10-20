from datetime import UTC, datetime, timedelta

import pytest

from custom_components.mobility_forecast.ev.models import (
    ChargingOpportunity,
    EVConfig,
    JourneyLeg,
    VehicleTelemetry,
)
from custom_components.mobility_forecast.ev.scheduling import recommend

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


@pytest.mark.parametrize("soc", [0, 10])
@pytest.mark.parametrize("available", [False, True])
def test_initial_reserve_shortfall(soc, available):
    windows = (
        [ChargingOpportunity("home", NOW, NOW + timedelta(hours=4), 11, 39.6)]
        if available
        else []
    )
    result, _, shortfall = recommend(
        EVConfig(60, 20, 11), VehicleTelemetry(soc, NOW, "fresh"), [], windows, NOW
    )
    assert result.status != "no_charge_needed"
    assert shortfall == NOW
    if available:
        assert result.target_soc == 15
        assert result.reason == "reserve_already_violated"
    else:
        assert result.status == "no_feasible_window"


@pytest.mark.parametrize("soc", [15, 16, 100])
def test_reserve_without_demand(soc):
    assert (
        recommend(
            EVConfig(60, 20, 11), VehicleTelemetry(soc, NOW, "fresh"), [], [], NOW
        )[0].status
        == "no_charge_needed"
    )


@pytest.mark.parametrize("soc,freshness", [(None, "unavailable"), (10, "stale")])
def test_missing_not_zero(soc, freshness):
    assert (
        recommend(
            EVConfig(60, 20, 11), VehicleTelemetry(soc, NOW, freshness), [], [], NOW
        )[0].status
        == "insufficient_data"
    )


def test_below_reserve_can_reach_public_charger_physically():
    leg = JourneyLeg(NOW, NOW + timedelta(minutes=20), 5, 20, "home", "appointment")
    window = ChargingOpportunity(
        "appointment", leg.arrival, leg.arrival + timedelta(hours=2), 11, 19.8
    )
    result, _, _ = recommend(
        EVConfig(60, 20, 11, charging_mode="appointments_only"),
        VehicleTelemetry(10, NOW, "fresh"),
        [leg],
        [window],
        NOW,
    )
    assert result.target_soc == 15
    assert result.reason == "reserve_already_violated"
    impossible = JourneyLeg(NOW, leg.arrival, 40, 20, "home", "appointment")
    assert (
        recommend(
            EVConfig(60, 20, 11),
            VehicleTelemetry(10, NOW, "fresh"),
            [impossible],
            [window],
            NOW,
        )[0].status
        == "no_feasible_window"
    )
