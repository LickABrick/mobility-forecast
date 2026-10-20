from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.ev.models import (
    EVConfig,
    JourneyLeg,
    VehicleTelemetry,
)
from custom_components.mobility_forecast.ev.opportunities import home_windows


def test_currently_away_preserves_return_in_current_window():
    now = datetime(2026, 10, 20, 19, tzinfo=UTC)
    leg = JourneyLeg(
        now + timedelta(minutes=30), now + timedelta(hours=1), 10, 30, "office", "home"
    )
    windows = home_windows(
        EVConfig(60, 20, 11),
        now,
        [leg],
        VehicleTelemetry(40, now, "fresh", location_state="not_home"),
    )
    assert windows[0].start == now + timedelta(hours=1)
    assert windows[0].end == datetime(2026, 10, 21, 6, 45, tzinfo=UTC)
    assert (
        home_windows(
            EVConfig(60, 20, 11),
            now,
            [],
            VehicleTelemetry(40, now, "fresh", location_state="not_home"),
        )
        == []
    )


def test_multiple_home_returns_do_not_erase_intermediate_window():
    now = datetime(2026, 10, 20, 8, tzinfo=UTC)
    legs = [
        JourneyLeg(
            now + timedelta(hours=a), now + timedelta(hours=b), 10, 60, "home", "home"
        )
        for a, b in [(2, 4), (6, 8)]
    ]
    windows = home_windows(
        EVConfig(
            60,
            20,
            11,
            home_window_start="08:00",
            home_window_end="20:00",
            session_overhead_minutes=0,
        ),
        now,
        legs,
        VehicleTelemetry(40, now, "fresh"),
    )
    assert [
        (w.start.hour, w.end.hour) for w in windows if w.start.date() == now.date()
    ] == [(8, 10), (12, 14), (16, 20)]
