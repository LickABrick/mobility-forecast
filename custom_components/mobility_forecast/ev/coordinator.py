"""EV-only background discovery. Mileage locks never await these providers."""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .charge_points import discover
from .energy import drive_energy, reserve_range
from .geocoding import resolve
from .models import ChargingRecommendation, EVConfig, JourneyLeg
from .opportunities import appointment_window, home_windows
from .providers import HTTP, ProviderError
from .scheduling import recommend
from .vehicle import telemetry


class EVRuntime:
    def __init__(self, parent):
        self.listeners = []
        self.parent = parent
        self.hass = parent.hass
        self.config = EVConfig.from_options(parent.entry.options)
        self.http = HTTP(self.hass, parent.store.payload.get("ev_cache", {}))
        self.task = None
        self.pending = None
        self.stopping = False
        self.lookup_signature = None
        self.public = []
        self.reason = None
        self.result = {
            "schema": 1,
            "status": "insufficient_data",
            "reason": "initializing",
            "recommendation": None,
            "alternative": None,
            "opportunities": [],
        }
        entities = [
            value
            for key, value in parent.entry.options.items()
            if key.endswith("_entity") and isinstance(value, str)
        ]
        if entities:
            parent.entry.async_on_unload(
                async_track_state_change_event(self.hass, entities, self.changed)
            )

    def changed(self, event):
        self.schedule()

    def schedule(self):
        if self.stopping or self.pending:
            return
        self.pending = self.hass.loop.call_later(2, self.launch)

    def launch(self):
        self.pending = None
        if not self.stopping and (self.task is None or self.task.done()):
            self.task = self.parent.entry.async_create_background_task(
                self.hass, self.update(), "EV forecast"
            )

    async def update(self):
        now = dt_util.utcnow().astimezone(ZoneInfo(self.hass.config.time_zone))
        cutoff = datetime.combine(now.date() + timedelta(days=7), time(), now.tzinfo)
        config = self.config
        vehicle = telemetry(
            self.hass, self.parent.entry.options, now, self.parent.readings
        )
        plans = {
            day: plan
            for day, plan in self.parent.plans.items()
            if now.date() <= day < cutoff.date()
        }
        legs = [
            leg
            for plan in plans.values()
            if plan.complete
            for leg in plan.legs
            if leg.arrival > now and leg.departure < cutoff
        ]
        stops = [
            stop
            for plan in plans.values()
            if plan.complete
            for stop in plan.stops
            if stop.departure > now
            and stop.arrival < cutoff
            and (
                stop.departure.astimezone(UTC) - stop.arrival.astimezone(UTC)
            ).total_seconds()
            >= config.minimum_appointment_minutes * 60
        ]
        signature = tuple(
            (stop.destination_identity, stop.arrival, stop.departure) for stop in stops
        )
        if (
            config.charging_mode != "home_only"
            and self.parent.entry.options.get("external_lookup_consent")
            and (signature != self.lookup_signature or not self.public)
        ):
            self.public = []
            self.reason = None
            for stop in stops[:10]:
                try:
                    coords, status = await resolve(self.http, stop.query)
                    if not coords:
                        self.reason = status
                        continue
                    points = await discover(
                        self.http, *coords, config.max_charger_distance_m, now
                    )
                    for point in points:
                        opportunity = appointment_window(config, stop, point, now)
                        if opportunity:
                            self.public.append(opportunity)
                except (ProviderError, ValueError, TypeError, KeyError):
                    self.reason = "charger_data_unavailable"
            self.lookup_signature = signature
            self.parent.store.payload["ev_cache"] = self.http.cache
            self.parent.store.schedule_routes()
        estimated = False
        # Retain daily demand without fabricating appointment stops. Coarse
        # day-end debit is an explicit estimate, not a precise travel departure.
        for day in self.parent.data.days[:7]:
            if day.day in plans and plans[day.day].complete and plans[day.day].legs:
                continue
            estimated = True
            if day.day == now.date():
                continue  # Unknown remaining portion of today's driving.
            departure = datetime.combine(day.day, time(23, 59), now.tzinfo)
            legs.append(
                JourneyLeg(
                    departure,
                    departure,
                    day.total_km,
                    0,
                    "estimated",
                    "estimated",
                    "daily_estimate",
                )
            )
        opportunities = home_windows(config, now, legs, vehicle) + [
            item for item in self.public if item.end > now and item.end < cutoff
        ]
        result, alternative, shortfall = recommend(
            config, vehicle, legs, opportunities, now, estimated
        )
        if config.charging_mode == "appointments_only" and not any(
            plan.complete and plan.legs for plan in plans.values()
        ):
            result = ChargingRecommendation(
                "insufficient_data", "insufficient_timing_information"
            )
        elif (
            self.reason == "charger_data_unavailable"
            and result.status == "no_feasible_window"
        ):
            result = ChargingRecommendation("provider_unavailable", self.reason)
        if any(not plan.complete for plan in plans.values()) and result.status in (
            "ready",
            "no_charge_needed",
        ):
            result = ChargingRecommendation(
                "insufficient_data", "calendar_itinerary_incomplete"
            )

        def serialized(value):
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {key: serialized(item) for key, item in value.items()}
            return value

        self.result = {
            "schema": 1,
            "status": result.status,
            "reason": result.reason,
            "config": {
                "charging_mode": config.charging_mode,
                "minimum_soc": config.minimum_soc,
                "preferred_max_soc": config.preferred_max_soc,
                "horizon_days": 7,
            },
            "telemetry": {
                "freshness": vehicle.freshness,
                "soc_percent": vehicle.current_soc_percent,
                "charging_state": vehicle.charging_state,
                "plugged_in": vehicle.plugged_in,
                "reported_range_km": vehicle.reported_range_km,
            },
            "estimated_range_km": reserve_range(
                config, vehicle.current_soc_percent, vehicle.consumption_kwh_per_100km
            )
            if vehicle.current_soc_percent is not None
            else None,
            "energy_demand_kwh": sum(
                drive_energy(day.total_km, config.consumption_kwh_per_100km)
                for day in self.parent.data.days[:7]
            ),
            "recommendation": serialized(asdict(result)),
            "alternative": serialized(asdict(alternative)) if alternative else None,
            "shortfall_at": shortfall.isoformat() if shortfall else None,
            "opportunities": [
                {
                    "source": item.source,
                    "start": item.start.isoformat(),
                    "end": item.end.isoformat(),
                    "power_kw": item.effective_power_kw,
                    "potential_battery_kwh": item.potential_battery_kwh,
                    "quality": item.quality,
                    "charger_distance_m": item.charger.distance_m
                    if item.charger
                    else None,
                }
                for item in sorted(opportunities, key=lambda item: item.start)[:24]
            ],
            "provider_status": self.reason,
        }
        for listener in self.listeners:
            listener()

    listeners = ()

    async def close(self):
        self.stopping = True
        if self.pending:
            self.pending.cancel()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
