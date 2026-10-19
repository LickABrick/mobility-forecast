"""Opt-in Waze adapter and conservative chronological itineraries."""

import asyncio
import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from .calendar_manager import Appointment
from .locations import Location

CACHE_TTL = 7 * 86400
MAX_CACHE = 512
MAX_REQUESTS = 60
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Route:
    distance_km: float
    duration_minutes: float


@dataclass(frozen=True)
class Plan:
    distance_km: float
    complete: bool
    missing: int = 0
    reason: str | None = None

    @property
    def retryable(self):
        return not self.complete and self.reason in (
            "route_request",
            "route_unavailable",
            "route_timeout",
        )


class RouteProvider(Protocol):
    async def get_route(
        self, origin: Location, destination: Location
    ) -> Route | None: ...


class RequestBudgetExceeded(Exception):
    """Defer the whole day to a later work cycle."""


class WazeProvider:
    def __init__(self, hass, region, cache=None):
        self.hass = hass
        self.region = region
        self.cache = cache if cache is not None else {}
        self.requests = 0
        self.inflight = {}
        self.consumers = {}
        self.slots = asyncio.Semaphore(3)
        self.failures = 0
        self.last_failure = None
        self.metrics = dict.fromkeys(
            (
                "route_lookups",
                "route_cache_hits",
                "route_cache_misses",
                "route_cache_expired",
                "route_requests_deduplicated",
                "route_cache_evictions",
            ),
            0,
        )
        self.prune_cache()

    def prune_cache(self):
        """Validate legacy v1 numeric payloads; expire before capacity eviction."""
        now = datetime.now(UTC).timestamp()
        for key, value in list(self.cache.items()):
            valid = (
                isinstance(key, str)
                and len(key) == 64
                and all(c in "0123456789abcdef" for c in key)
            )
            valid = (
                valid
                and isinstance(value, dict)
                and all(
                    isinstance(value.get(field), (int, float))
                    and not isinstance(value.get(field), bool)
                    and math.isfinite(value[field])
                    for field in ("at", "km", "minutes")
                )
            )
            if valid and 0 < value["at"] <= now and now - value["at"] >= CACHE_TTL:
                self.metrics["route_cache_expired"] += 1
            if (
                not valid
                or not (
                    0 < value["at"] <= now and value["km"] > 0 and value["minutes"] >= 0
                )
                or now - value["at"] >= CACHE_TTL
            ):
                del self.cache[key]
        while len(self.cache) > MAX_CACHE:
            self.metrics["route_cache_evictions"] += 1
            del self.cache[min(self.cache, key=lambda k: self.cache[k]["at"])]

    @property
    def statistics(self):
        return {
            **self.metrics,
            "route_cache_entries": len(self.cache),
            "waze_requests": self.requests,
            "waze_failures": self.failures,
        }

    async def get_route(self, origin, destination):
        self.metrics["route_lookups"] += 1
        identity = self.cache_key(origin.identifier, destination.identifier)
        if identity not in self.inflight:
            # Planner has three workers. Refuse unbounded standalone fan-out too;
            # no service task is created until a slot is available.
            await self.slots.acquire()
            if identity not in self.inflight:
                self.inflight[identity] = asyncio.create_task(
                    self._get_route(origin, destination)
                )
                self.consumers[identity] = 0
            else:
                self.slots.release()
        if self.consumers[identity]:
            self.metrics["route_requests_deduplicated"] += 1
        task = self.inflight[identity]
        self.consumers[identity] += 1
        try:
            return await asyncio.shield(task)
        finally:
            self.consumers[identity] -= 1
            if not self.consumers[identity]:
                # Last consumer owns cleanup. A cancelled consumer cannot kill
                # work another day still needs; no orphan survives cycle exit.
                self.inflight.pop(identity, None)
                self.consumers.pop(identity, None)
                if not task.done():
                    task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                finally:
                    self.slots.release()

    async def async_close(self):
        tasks = list(self.inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def cache_key(self, origin, destination):
        """Keep the v1 provider/region/units/vehicle format for compatibility."""
        return hashlib.sha256(
            f"waze|{self.region}|metric|car|{origin}|{destination}".encode()
        ).hexdigest()

    async def _get_route(self, origin, destination):
        if origin.identifier == destination.identifier:
            return Route(0, 0)
        key = self.cache_key(origin.identifier, destination.identifier)
        now = datetime.now(UTC).timestamp()
        cached = self.cache.get(key)
        if cached is None:
            # Only try known equivalent original spellings, never rounded old
            # coordinates or fuzzy addresses. Preserve other v1 entries as-is.
            for a in (origin.identifier, origin.legacy_identifier):
                for b in (destination.identifier, destination.legacy_identifier):
                    if a is not None and b is not None:
                        legacy = self.cache.get(self.cache_key(a, b))
                        if legacy is not None:
                            cached = legacy
                            break
                if cached is not None:
                    break
        if cached and 0 <= now - cached["at"] < CACHE_TTL:
            self.metrics["route_cache_hits"] += 1
            return Route(cached["km"], cached["minutes"])
        if cached and now - cached["at"] >= CACHE_TTL:
            # Entries may expire during a long-lived provider cycle too.
            self.prune_cache()
        self.metrics["route_cache_misses"] += 1
        if self.requests >= MAX_REQUESTS:
            self.last_failure = "request_budget"
            raise RequestBudgetExceeded
        if self.region not in (
            "eu",
            "us",
            "na",
            "il",
            "au",
        ) or not self.hass.services.has_service("waze_travel_time", "get_travel_times"):
            self.last_failure = "provider_unavailable"
            return None
        self.requests += 1
        try:
            async with asyncio.timeout(20):
                response = await self.hass.services.async_call(
                    "waze_travel_time",
                    "get_travel_times",
                    {
                        "origin": origin.query,
                        "destination": destination.query,
                        "region": self.region,
                        "realtime": False,
                        "vehicle_type": "car",
                        "units": "metric",
                        "incl_filter": [],
                        "excl_filter": [],
                    },
                    blocking=True,
                    return_response=True,
                )
            routes = []
            for row in (response or {}).get("routes", []):
                try:
                    distance, duration = float(row["distance"]), float(row["duration"])
                except (KeyError, TypeError, ValueError):
                    continue
                if (
                    math.isfinite(distance)
                    and math.isfinite(duration)
                    and distance > 0
                    and duration >= 0
                ):
                    routes.append(Route(distance, duration))
            if not routes:
                self.failures += 1
                self.last_failure = "route_unavailable"
                return None
            route = min(routes, key=lambda r: r.duration_minutes)
            self.cache[key] = {
                "at": now,
                "km": route.distance_km,
                "minutes": route.duration_minutes,
            }
            self.prune_cache()
            return route
        except Exception as err:
            self.failures += 1
            self.last_failure = (
                "route_timeout"
                if isinstance(err, TimeoutError)
                else "route_unavailable"
            )
            _LOGGER.debug(
                "Calendar stage=route_request exception=%s failures=%d",
                type(err).__name__,
                self.failures,
            )
            # Service exceptions may include addresses; do not log them.
            return None


async def plan_journeys(events, home, provider: RouteProvider):
    """Three fixed workers process independent days; each chain stays ordered."""
    days = sorted({event.start.date() for event in events})
    # Overnight events are handled as one conservative group so their affected
    # dates cannot race with independently processed next-day appointments.
    if any(event.end.date() != event.start.date() for event in events):
        return await _plan_journeys(events, home, provider)
    queue: asyncio.Queue[date] = asyncio.Queue()
    for day in days:
        queue.put_nowait(day)
    results = {}

    async def worker():
        while not queue.empty():
            day = queue.get_nowait()
            subset = [event for event in events if event.start.date() == day]
            results.update(await _plan_journeys(subset, home, provider))

    async with asyncio.TaskGroup() as tasks:
        for _ in range(min(3, len(days))):
            tasks.create_task(worker())
    return results


async def _plan_journeys(events, home, provider: RouteProvider):
    events = [
        event for event in events if not event.virtual and event.location is not None
    ]
    grouped: dict[date, list[Appointment]] = {}
    for event in events:
        day = event.start.date()
        # Mark every affected date, not only departure day, for overnight events.
        from datetime import timedelta

        while day <= event.end.date():
            if day < event.end.date() or event.end.time().isoformat() != "00:00:00":
                grouped.setdefault(day, []).append(event)
            day += timedelta(days=1)
    plans = {}
    for day, appointments in grouped.items():
        appointments.sort(key=lambda e: (e.start.astimezone(UTC), e.identifier))
        # Non-routable events were excluded; physical all-day/overnight
        # itineraries still have unsupported travel semantics.
        invalid = any(
            e.location is None
            or e.all_day
            or e.start.date() != day
            or e.end.date() != day
            for e in appointments
        )
        overlap = any(
            a.end.astimezone(UTC) > b.start.astimezone(UTC) and a.location != b.location
            for index, a in enumerate(appointments)
            for b in appointments[index + 1 :]
        )
        # Merge consecutive same-location appointments, including nested events.
        merged: list[Appointment] = []
        from dataclasses import replace

        for event in appointments:
            if merged and merged[-1].location == event.location:
                merged[-1] = replace(
                    merged[-1],
                    end=max(
                        merged[-1].end,
                        event.end,
                        key=lambda stamp: stamp.astimezone(UTC),
                    ),
                )
            else:
                merged.append(event)
        appointments = merged
        if invalid or overlap:
            plans[day] = Plan(
                0,
                False,
                1,
                (
                    "unsupported_all_day"
                    if any(e.all_day for e in appointments)
                    else "unsupported_overnight"
                )
                if invalid
                else "conflicting_appointments",
            )
            continue
        total = 0.0
        previous = home
        last_end = None
        complete = True
        reason = None
        for event in appointments:
            assert event.location is not None  # invalid itineraries returned above
            route = await provider.get_route(previous, event.location)
            if route is None:
                complete = False
                reason = (
                    "route_timeout"
                    if getattr(provider, "last_failure", None) == "route_timeout"
                    else "route_unavailable"
                )
                break
            if (
                last_end is not None
                and route.duration_minutes
                > (
                    event.start.astimezone(UTC) - last_end.astimezone(UTC)
                ).total_seconds()
                / 60
            ):
                complete = False
                reason = "impossible_itinerary"
                break
            total += route.distance_km
            previous = event.location
            last_end = event.end
        if complete:
            route = await provider.get_route(previous, home)
            if route is not None:
                total += route.distance_km
            else:
                complete = False
                reason = (
                    "route_timeout"
                    if getattr(provider, "last_failure", None) == "route_timeout"
                    else "route_unavailable"
                )
        plans[day] = Plan(
            total if complete else 0,
            complete,
            int(not complete),
            reason,
        )
    return plans
