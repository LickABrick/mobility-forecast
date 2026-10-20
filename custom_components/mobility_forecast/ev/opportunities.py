"""Pure windows constrained to stops and local home availability assumptions."""

from datetime import UTC, datetime, time, timedelta

from .models import ChargingOpportunity


def window(config, source, start, end, now, stop_identity="home", charger=None):
    start = max(start.astimezone(UTC), now.astimezone(UTC))
    end = end.astimezone(UTC) - timedelta(minutes=config.session_overhead_minutes)
    power = min(
        config.max_ac_charge_power_kw,
        charger.ac_power_kw if charger else config.max_ac_charge_power_kw,
    )
    hours = (end - start).total_seconds() / 3600
    if hours <= 0 or power <= 0:
        return None
    return ChargingOpportunity(
        source,
        start,
        end,
        power,
        hours * power * 0.9,
        stop_identity,
        charger,
        "potential_public_availability" if charger else "assumed_home_availability",
    )


def home_windows(config, now, legs, telemetry):
    if config.charging_mode == "appointments_only":
        return []
    result = []
    for offset in range(-1, 7):
        day = now.date() + timedelta(days=offset)
        start = datetime.combine(
            day, time.fromisoformat(config.home_window_start), now.tzinfo
        )
        end = datetime.combine(
            day, time.fromisoformat(config.home_window_end), now.tzinfo
        )
        if end <= start:
            end = datetime.combine(
                day + timedelta(days=1),
                time.fromisoformat(config.home_window_end),
                now.tzinfo,
            )
        start = max(start.astimezone(UTC), now.astimezone(UTC))
        end = min(
            end.astimezone(UTC),
            datetime.combine(
                now.date() + timedelta(days=7), time(), now.tzinfo
            ).astimezone(UTC),
        )
        if start >= end or (
            start <= now.astimezone(UTC) and telemetry.location_state == "not_home"
        ):
            continue
        # Home-to-home chain: all time from first departure to final return is away.
        for day_legs in (
            {
                leg.departure.astimezone(now.tzinfo).date(): [
                    item
                    for item in legs
                    if item.departure.astimezone(now.tzinfo).date()
                    == leg.departure.astimezone(now.tzinfo).date()
                ]
                for leg in legs
            }
        ).values():
            away_start = min(item.departure for item in day_legs).astimezone(UTC)
            away_end = max(item.arrival for item in day_legs).astimezone(UTC)
            if start < away_end and end > away_start:
                if start < away_start:
                    end = min(end, away_start)
                else:
                    start = max(start, away_end)
        opportunity = window(config, "home", start, end, now)
        if opportunity:
            result.append(opportunity)
    return result


def appointment_window(config, stop, charger, now):
    if (
        config.charging_mode == "home_only"
        or (
            stop.departure.astimezone(UTC) - stop.arrival.astimezone(UTC)
        ).total_seconds()
        < config.minimum_appointment_minutes * 60
        or charger.distance_m > config.max_charger_distance_m
    ):
        return None
    return window(
        config,
        "public",
        stop.arrival,
        stop.departure,
        now,
        stop.destination_identity,
        charger,
    )
