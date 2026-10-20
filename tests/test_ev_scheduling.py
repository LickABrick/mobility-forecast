from dataclasses import replace
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.ev.models import (
    ChargingOpportunity,
    EVConfig,
    JourneyLeg,
    VehicleTelemetry,
)
from custom_components.mobility_forecast.ev.opportunities import home_windows
from custom_components.mobility_forecast.ev.scheduling import recommend


def test_chronology_and_reserve():
    now = datetime(2026, 1, 1, 18, tzinfo=UTC)
    config = EVConfig(60, 20, 11)
    telemetry = VehicleTelemetry(40, now, "fresh")
    leg = JourneyLeg(
        now + timedelta(hours=14), now + timedelta(hours=15), 150, 60, "home", "office"
    )
    windows = home_windows(config, now, [leg], telemetry)
    result, alternative, shortfall = recommend(config, telemetry, [leg], windows, now)
    assert result.status == "estimated"
    assert result.target_soc <= 80
    assert result.end <= leg.departure
    assert result.battery_energy_kwh >= 15
    assert shortfall == leg.departure
    late = ChargingOpportunity(
        "public", leg.arrival, leg.arrival + timedelta(hours=2), 11, 19
    )
    assert (
        recommend(config, telemetry, [leg], [late], now)[0].status
        == "no_feasible_window"
    )
    assert (
        recommend(config, replace(telemetry, freshness="stale"), [leg], windows, now)[
            0
        ].status
        == "insufficient_data"
    )
    assert (
        recommend(config, telemetry, [], windows, now)[0].status == "no_charge_needed"
    )


def test_exception_target_and_vehicle_limit():
    now = datetime(2026, 1, 1, 18, tzinfo=UTC)
    config = EVConfig(60, 20, 11)
    telemetry = VehicleTelemetry(40, now, "fresh")
    leg = JourneyLeg(
        now + timedelta(hours=14), now + timedelta(hours=15), 210, 60, "home", "office"
    )
    windows = home_windows(config, now, [leg], telemetry)
    assert (
        recommend(config, telemetry, [leg], windows, now)[0].status
        == "no_feasible_window"
    )
    result = recommend(
        replace(config, allow_above_preferred_soc=True), telemetry, [leg], windows, now
    )[0]
    assert result.reason == "exceptional_target" and result.target_soc == 85
    assert (
        recommend(
            replace(config, allow_above_preferred_soc=True),
            replace(telemetry, vehicle_charge_limit_percent=80),
            [leg],
            windows,
            now,
        )[0].status
        == "no_feasible_window"
    )
