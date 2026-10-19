"""Opt-in Waze adapter and conservative chronological itineraries."""

import asyncio
import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from .locations import Location

CACHE_TTL = 7 * 86400
MAX_CACHE = 512
MAX_REQUESTS = 60


@dataclass(frozen=True)
class Route:
    distance_km: float
    duration_minutes: float


@dataclass(frozen=True)
class Plan:
    distance_km: float
    complete: bool
    missing: int = 0


class RouteProvider(Protocol):
    async def get_route(
        self, origin: Location, destination: Location
    ) -> Route | None: ...


class WazeProvider:
    def __init__(self, hass, region, cache=None):
        self.hass = hass
        self.region = region
        self.cache = cache if cache is not None else {}
        self.requests = 0
        # Persisted cache entries are untrusted input after upgrades/restores.
        for key, value in list(self.cache.items()):
            try:
                valid = (
                    all(math.isfinite(float(value[k])) for k in ("at", "km", "minutes"))
                    and value["km"] > 0
                    and value["minutes"] >= 0
                )
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                del self.cache[key]
        while len(self.cache) > MAX_CACHE:
            del self.cache[min(self.cache, key=lambda k: self.cache[k]["at"])]

    async def get_route(self, origin, destination):
        if origin.identifier == destination.identifier:
            return Route(0, 0)
        key = hashlib.sha256(
            f"waze|{self.region}|metric|car|{origin.identifier}|{destination.identifier}".encode()
        ).hexdigest()
        now = datetime.now(UTC).timestamp()
        cached = self.cache.get(key)
        if cached and now - cached["at"] < CACHE_TTL:
            return Route(cached["km"], cached["minutes"])
        if (
            self.region not in ("eu", "us", "na", "il", "au")
            or not self.hass.services.has_service(
                "waze_travel_time", "get_travel_times"
            )
            or self.requests >= MAX_REQUESTS
        ):
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
                return None
            route = min(routes, key=lambda r: r.duration_minutes)
            self.cache[key] = {
                "at": now,
                "km": route.distance_km,
                "minutes": route.duration_minutes,
            }
            while len(self.cache) > MAX_CACHE:
                del self.cache[min(self.cache, key=lambda k: self.cache[k]["at"])]
            return route
        except Exception:
            # Service exceptions may include addresses; do not log them.
            return None


async def plan_journeys(events, home, provider: RouteProvider):
    grouped = {}
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
        appointments.sort(key=lambda e: e.start)
        # Unknown/all-day/midnight appointments invalidate the assumed daily chain.
        invalid = any(
            e.location is None or e.all_day or e.end.date() != day for e in appointments
        )
        overlap = any(
            a.end > b.start and a.location != b.location
            for index, a in enumerate(appointments)
            for b in appointments[index + 1 :]
        )
        # Merge consecutive same-location appointments, including nested events.
        merged = []
        from dataclasses import replace

        for event in appointments:
            if merged and merged[-1].location == event.location:
                merged[-1] = replace(merged[-1], end=max(merged[-1].end, event.end))
            else:
                merged.append(event)
        appointments = merged
        if invalid or overlap:
            plans[day] = Plan(0, False, 1)
            continue
        total = 0.0
        previous = home
        last_end = None
        complete = True
        for event in appointments:
            route = await provider.get_route(previous, event.location)
            if route is None or (
                last_end is not None
                and route.duration_minutes
                > (event.start - last_end).total_seconds() / 60
            ):
                complete = False
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
        plans[day] = Plan(total, complete, int(not complete))
    return plans
