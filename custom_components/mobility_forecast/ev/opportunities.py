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
        grouped = {}
        for leg in legs:
            if leg.quality == "daily_estimate":
                continue
            grouped.setdefault(leg.departure.astimezone(now.tzinfo).date(), []).append(
                leg
            )
        away = [
            (
                min(item.departure.astimezone(UTC) for item in items),
                max(item.arrival.astimezone(UTC) for item in items),
            )
            for items in grouped.values()
        ]
        segments = [(start, end)]
        for away_start, away_end in sorted(away):
            retained = []
            for left, right in segments:
                if away_end <= left or away_start >= right:
                    retained.append((left, right))
                else:
                    if left < away_start:
                        retained.append((left, away_start))
                    if away_end < right:
                        retained.append((away_end, right))
            segments = retained
        for left, right in segments:
            opportunity = window(config, "home", left, right, now)
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
