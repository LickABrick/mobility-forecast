from dataclasses import replace
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.calendar_storage import restore
from custom_components.mobility_forecast.ev.demand import reconcile
from custom_components.mobility_forecast.ev.geocoding import parse_address
from custom_components.mobility_forecast.ev.models import (
    EVConfig,
    JourneyLeg,
    VehicleTelemetry,
)
from custom_components.mobility_forecast.ev.opportunities import home_windows
from custom_components.mobility_forecast.models import DailyForecast
from custom_components.mobility_forecast.routing import Plan


def test_energy_reconciliation_does_not_drop_historical_extra():
    now = datetime(2026, 1, 1, 8, tzinfo=UTC)
    leg = JourneyLeg(
        now + timedelta(hours=1), now + timedelta(hours=2), 30, 60, "home", "office"
    )
    forecast = DailyForecast(now.date(), 180, 180, 150, 200)
    legs, extra = reconcile(
        [forecast], {now.date(): Plan(30, True, legs=(leg,))}, [], now
    )
    assert sum(item.distance_km for item in legs) == 180
    assert extra == [{"date": "2026-01-01", "distance_km": 150}]
    assert (
        reconcile(
            [replace(forecast, total_km=30)],
            {now.date(): Plan(30, True, legs=(leg,))},
            [],
            now,
        )[1]
        == []
    )


def test_home_window_keeps_both_sides():
    now = datetime(2026, 1, 1, 8, tzinfo=UTC)
    config = EVConfig(
        60,
        20,
        11,
        home_window_start="08:00",
        home_window_end="20:00",
        session_overhead_minutes=0,
    )
    leg = JourneyLeg(
        now + timedelta(hours=2), now + timedelta(hours=4), 20, 120, "home", "home"
    )
    windows = home_windows(config, now, [leg], VehicleTelemetry(40, now, "fresh"))
    assert [
        (item.start.hour, item.end.hour)
        for item in windows
        if item.start.date() == now.date()
    ] == [(8, 10), (12, 20)]


def test_optional_corrupt_plans_are_ignored():
    now = datetime.now(UTC)
    assert restore(None, "identity", now) == {}
    assert (
        restore(
            {now.date().isoformat(): {"distance_km": float("nan")}}, "identity", now
        )
        == {}
    )


def test_pdok_without_postcode_exact_locality():
    payload = {
        "response": {
            "docs": [
                {
                    "type": "adres",
                    "straatnaam": "Stationsstraat",
                    "huisnummer": 12,
                    "woonplaatsnaam": "Doetinchem",
                    "centroide_ll": "POINT(6.3 51.96)",
                }
            ]
        }
    }
    assert parse_address(payload, "Stationsstraat 12, Doetinchem") == (51.96, 6.3)
    assert parse_address(payload, "Stationsstraat 12, Arnhem") is None
    assert parse_address(payload, "Stationsstraat 13, Doetinchem") is None
