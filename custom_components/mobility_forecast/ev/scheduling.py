"""Deterministic first-shortfall AC session selection, never charger control."""

from datetime import UTC, timedelta

from .energy import battery_energy, charge_estimate, drive_energy
from .models import ChargingRecommendation


def recommend(
    config, telemetry, legs, opportunities, now, estimated=False, untimed_km=0
):
    if (
        telemetry.current_soc_percent is None
        or telemetry.freshness != "fresh"
        or telemetry.soc_observed_at is None
    ):
        return (
            ChargingRecommendation("insufficient_data", "soc_" + telemetry.freshness),
            None,
            None,
        )
    capacity = config.usable_capacity_kwh
    reserve = battery_energy(capacity, config.minimum_soc)
    initial = battery_energy(capacity, telemetry.current_soc_percent)
    anchor = max(now.astimezone(UTC), telemetry.soc_observed_at.astimezone(UTC))
    if any(leg.departure < anchor < leg.arrival for leg in legs):
        return (
            ChargingRecommendation("insufficient_data", "journey_in_progress"),
            None,
            None,
        )
    future = sorted(
        (leg for leg in legs if leg.departure >= anchor),
        key=lambda leg: (leg.departure, leg.arrival, leg.destination_identity),
    )
    remaining = initial
    already_violated = initial < reserve
    shortfall = anchor if already_violated else None
    for leg in future:
        remaining -= drive_energy(
            leg.distance_km,
            telemetry.consumption_kwh_per_100km or config.consumption_kwh_per_100km,
        )
        if remaining < reserve and not already_violated:
            shortfall = leg.departure
            break
    if untimed_km > 0:
        if already_violated:
            return (
                ChargingRecommendation(
                    "insufficient_data",
                    "reserve_already_violated_untimed_demand",
                    "estimated",
                ),
                None,
                anchor,
            )
        total_need = drive_energy(
            sum(leg.distance_km for leg in future) + untimed_km,
            telemetry.consumption_kwh_per_100km or config.consumption_kwh_per_100km,
        )
        if initial - total_need < reserve and not already_violated:
            # Energy demand is real, but no artificial day-end timestamp can
            # prove a session precedes it. Do not advertise a false deadline.
            return (
                ChargingRecommendation(
                    "insufficient_data", "untimed_demand_reserve_risk", "estimated"
                ),
                None,
                None,
            )
    if shortfall is None:
        return (
            ChargingRecommendation(
                "no_charge_needed",
                "reserve_preserved",
                "estimated" if estimated else "timed",
            ),
            None,
            None,
        )
    allowed = min(
        config.absolute_max_soc,
        telemetry.vehicle_charge_limit_percent
        if telemetry.vehicle_charge_limit_percent is not None
        else 100,
    )
    normal = min(config.preferred_max_soc, allowed)
    candidates = []
    for opportunity in opportunities:
        if opportunity.start < anchor or (
            not already_violated and opportunity.start >= shortfall
        ):
            continue
        end = opportunity.end if already_violated else min(opportunity.end, shortfall)
        # A selected window cannot overlap driving; verify reserve to reach it.
        before = [leg for leg in future if leg.arrival <= opportunity.start]
        if any(
            leg.departure < end and leg.arrival > opportunity.start for leg in future
        ):
            continue
        used = sum(
            drive_energy(
                leg.distance_km,
                telemetry.consumption_kwh_per_100km or config.consumption_kwh_per_100km,
            )
            for leg in before
        )
        energy = initial - used
        if energy < 0 or (not already_violated and energy < reserve):
            continue
        # Cover until the next usable later window, or the horizon if none.
        next_window = min(
            (
                item.start
                for item in opportunities
                if item.start >= end and item.start > opportunity.start
            ),
            default=None,
        )
        segment = [
            leg
            for leg in future
            if leg.departure >= end
            and (next_window is None or leg.departure < next_window)
        ]
        # Always include the first reserve violation, even if another window is
        # too late to reach safely. A candidate must fix the immediate problem.
        immediate = [
            leg for leg in future if leg.departure >= end and leg.departure <= shortfall
        ]
        need = max(
            sum(
                drive_energy(
                    leg.distance_km,
                    telemetry.consumption_kwh_per_100km
                    or config.consumption_kwh_per_100km,
                )
                for leg in segment
            ),
            sum(
                drive_energy(
                    leg.distance_km,
                    telemetry.consumption_kwh_per_100km
                    or config.consumption_kwh_per_100km,
                )
                for leg in immediate
            ),
        )
        required = 100 * (reserve + need) / capacity
        limit = (
            allowed
            if config.allow_above_preferred_soc and required > normal
            else normal
        )
        target = max(energy * 100 / capacity, required)
        if target > limit + 1e-8:
            continue
        pre_soc = energy * 100 / capacity
        battery, grid, minutes = charge_estimate(
            capacity,
            pre_soc,
            target,
            config.max_ac_charge_power_kw,
            min(opportunity.effective_power_kw, telemetry.charging_power_kw)
            if telemetry.charging_state == "charging"
            and telemetry.charging_power_kw
            and opportunity.start <= anchor
            and opportunity.source == "home"
            else opportunity.effective_power_kw,
        )
        if minutes <= 0 or minutes * 60 > (end - opportunity.start).total_seconds():
            continue
        start = (
            opportunity.start if already_violated else end - timedelta(minutes=minutes)
        )
        if already_violated:
            end = start + timedelta(minutes=minutes)
        candidates.append(
            ChargingRecommendation(
                "estimated" if estimated or opportunity.source == "home" else "ready",
                "reserve_already_violated"
                if already_violated
                else "exceptional_target"
                if target > normal
                else "charge_before_reserve_shortfall",
                "estimated" if estimated or opportunity.source == "home" else "timed",
                start,
                end,
                opportunity.source,
                pre_soc,
                target,
                battery,
                grid,
                minutes,
                shortfall,
                opportunity.charger.distance_m if opportunity.charger else None,
            )
        )
    if not candidates:
        return (
            ChargingRecommendation(
                "no_feasible_window",
                "insufficient_energy_before_next_charger",
                "estimated" if estimated else "timed",
                deadline=shortfall,
            ),
            None,
            shortfall,
        )
    candidates.sort(
        key=lambda candidate: (
            (candidate.battery_energy_kwh < config.minimum_useful_charge_kwh),
            (candidate.target_soc if config.prefer_long_sessions else 0),
            -candidate.start.timestamp(),
            candidate.location_type,
        )
    )
    return (
        candidates[0],
        next(
            (
                candidate
                for candidate in candidates[1:]
                if candidate.start != candidates[0].start
                or candidate.location_type != candidates[0].location_type
            ),
            None,
        ),
        shortfall,
    )
