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
from .models import ChargingRecommendation, EVConfig
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
        self.revision = 0
        self.dirty = False
        self.lookup_signature = None
        self.lookup_at = None
        self.destination_results = {}
        self.destination_attempts = {}
        self.destination_retry = {}
        self.discovery_timer = None
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
        self.revision += 1
        self.dirty = True
        if self.stopping or self.pending:
            return
        self.pending = self.hass.loop.call_later(2, self.launch)

    def launch(self):
        self.pending = None
        if not self.stopping and (self.task is None or self.task.done()):
            self.task = self.parent.entry.async_create_background_task(
                self.hass, self.worker(), "EV forecast"
            )

    async def worker(self):
        try:
            while self.dirty and not self.stopping:
                self.dirty = False
                await self.update()
        except asyncio.CancelledError:
            raise
        except Exception:
            if not self.stopping:
                self.result = {
                    "schema": 1,
                    "status": "insufficient_data",
                    "reason": "processing_error",
                    "recommendation": None,
                    "alternative": None,
                    "opportunities": [],
                }
                for listener in tuple(self.listeners):
                    listener()

    async def update(self):
        revision = self.revision
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
            and (
                signature != self.lookup_signature
                or self.lookup_at is None
                or (now - self.lookup_at).total_seconds() >= 86400
            )
        ):
            if signature != self.lookup_signature:
                retained = {stop.destination_identity for stop in stops}
                self.destination_results = {
                    key: value
                    for key, value in self.destination_results.items()
                    if key in retained
                }
                self.destination_attempts = {
                    key: value
                    for key, value in self.destination_attempts.items()
                    if key in retained
                }
                self.destination_retry = {
                    key: value
                    for key, value in self.destination_retry.items()
                    if key in retained
                }
            if self.lookup_at and (now - self.lookup_at).total_seconds() >= 86400:
                self.destination_results = {}
            self.reason = None
            destinations = {}
            for stop in sorted(stops, key=lambda item: item.arrival):
                destinations.setdefault(stop.destination_identity, stop)
            pending = [
                stop
                for identity, stop in destinations.items()
                if identity not in self.destination_results
                and self.destination_attempts.get(identity, 0) < 3
                and self.destination_retry.get(identity, now) <= now
            ]
            for stop in pending[:10]:
                identity = stop.destination_identity
                try:
                    coords, status = await resolve(self.http, stop.query)
                    points = (
                        await discover(
                            self.http, *coords, config.max_charger_distance_m, now
                        )
                        if coords
                        else []
                    )
                    self.destination_results[identity] = points
                    if not coords:
                        self.reason = status
                except (ProviderError, ValueError, TypeError, KeyError):
                    self.reason = "charger_data_unavailable"
                    self.destination_attempts[identity] = (
                        self.destination_attempts.get(identity, 0) + 1
                    )
                    self.destination_retry[identity] = now + timedelta(
                        seconds=300
                        if self.http.cooldown
                        else 60 * self.destination_attempts[identity]
                    )
            self.public = []
            for stop in stops:
                for point in self.destination_results.get(
                    stop.destination_identity, []
                ):
                    opportunity = appointment_window(config, stop, point, now)
                    if opportunity:
                        self.public.append(opportunity)
            remaining = [
                identity
                for identity in destinations
                if identity not in self.destination_results
                and self.destination_attempts.get(identity, 0) < 3
            ]
            if remaining:
                self.reason = self.reason or "lookup_budget_deferred"
                if self.discovery_timer:
                    self.discovery_timer.cancel()
                self.discovery_timer = self.hass.loop.call_later(60, self.schedule)
            self.lookup_signature = signature
            self.lookup_at = now if not remaining else None
            self.parent.store.payload["ev_cache"] = self.http.cache
            self.parent.store.schedule_routes()
        from .demand import reconcile

        legs, unallocated = reconcile(
            self.parent.data.days, plans, getattr(self.parent, "history_cache", []), now
        )
        estimated = bool(unallocated)
        opportunities = home_windows(config, now, legs, vehicle) + [
            item for item in self.public if item.end > now and item.end < cutoff
        ]
        result, alternative, shortfall = recommend(
            config,
            vehicle,
            legs,
            opportunities,
            now,
            estimated,
            sum(item["distance_km"] for item in unallocated),
        )
        if any(plan.complete and not plan.legs for plan in plans.values()):
            result = ChargingRecommendation(
                "insufficient_data", "restored_itinerary_pending_verification"
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
        if self.parent.data.quality == "insufficient":
            result = ChargingRecommendation(
                "insufficient_data", "mileage_history_insufficient"
            )
        if any(not plan.complete for plan in plans.values()) and result.status in (
            "ready",
            "estimated",
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

        if self.stopping or revision != self.revision:
            self.dirty = True
            return
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
            "unallocated_demand": unallocated,
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
        if self.discovery_timer:
            self.discovery_timer.cancel()
        if self.pending:
            self.pending.cancel()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
