"""Bounded, cache-aware Geoapify geocoding and routing adapters.

This module contains no HTTP implementation. Private locations, coordinates and
credentials are passed only to injected transports and excluded from representations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .domain.event_locations import (
    EventLocationFailure,
    EventLocationFailureCategory,
    EventLocationRequest,
    EventLocationResult,
    EventLocationSuccess,
)
from .domain.models import Coordinates, DataQuality, Route
from .domain.routing import (
    RouteCache,
    RouteFailure,
    RouteFailureCategory,
    RouteRequest,
    RouteResult,
    RouteSuccess,
    route_with_cache,
)
from .openrouteservice import GeocodeCache, ProviderRefreshBudget
from .provider_guardrails import GeocodeCacheKey, build_geocode_cache_key
from .route_provider_config import ProfileRouteConfig, RouteProviderKind

GEOAPIFY_PROVIDER = "geoapify"
GEOAPIFY_ROUTES_CACHE_NAMESPACE = "geoapify:routing:v1"
GEOAPIFY_GEOCODING_CACHE_NAMESPACE = "geoapify:geocoding:v1"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class GeoapifyGeocodeQuery:
    """Private geocoding query delivered only to the injected transport."""

    api_key: str = field(repr=False)
    location_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("API key must not be empty")
        if not self.location_text.strip():
            raise ValueError("location text must not be empty")


@dataclass(frozen=True, slots=True)
class GeoapifyGeocodeResponse:
    """Validated Geoapify geocode coordinates hidden from representations."""

    coordinates: Coordinates = field(repr=False)


@dataclass(frozen=True, slots=True)
class GeoapifyGeocodeFailure:
    """Sanitized geocoding failure without provider response details."""

    category: EventLocationFailureCategory
    occurred_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.occurred_at, "occurred_at")

    @property
    def retryable(self) -> bool:
        return self.category in (
            EventLocationFailureCategory.RATE_LIMITED,
            EventLocationFailureCategory.TRANSIENT,
        )


type GeoapifyGeocodeTransportResult = GeoapifyGeocodeResponse | GeoapifyGeocodeFailure


class GeoapifyGeocodeTransport(Protocol):
    """Injected Geoapify geocoding I/O boundary."""

    async def geocode(
        self, query: GeoapifyGeocodeQuery
    ) -> GeoapifyGeocodeTransportResult:
        """Return validated coordinates or a sanitized failure."""
        ...


@dataclass(frozen=True, slots=True)
class GeoapifyRouteQuery:
    """Minimal route query with private coordinates omitted from representations."""

    origin: Coordinates = field(repr=False)
    destination: Coordinates = field(repr=False)
    avoid_tolls: bool
    avoid_highways: bool
    depart_at: datetime | None

    def __post_init__(self) -> None:
        if self.origin == self.destination:
            raise ValueError("origin and destination coordinates must differ")
        if self.depart_at is not None:
            _require_aware(self.depart_at, "depart_at")


@dataclass(frozen=True, slots=True)
class GeoapifyRouteResponse:
    """Validated route values independent from HTTP response shape."""

    distance_m: int
    duration_s: int
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_positive_int(self.distance_m, "distance_m")
        _require_positive_int(self.duration_s, "duration_s")
        _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class GeoapifyRouteFailure:
    """Sanitized routing failure without response or request data."""

    category: RouteFailureCategory
    occurred_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.occurred_at, "occurred_at")

    @property
    def retryable(self) -> bool:
        return self.category in (
            RouteFailureCategory.RATE_LIMITED,
            RouteFailureCategory.TRANSIENT,
        )


type GeoapifyRouteTransportResult = GeoapifyRouteResponse | GeoapifyRouteFailure


class GeoapifyRouteTransport(Protocol):
    """Injected Geoapify routing I/O boundary."""

    async def route(self, query: GeoapifyRouteQuery) -> GeoapifyRouteTransportResult:
        """Return validated route data or a sanitized failure."""
        ...


class GeoapifyRouteAdapter:
    """Translate provider-neutral requests to the Geoapify transport contract."""

    def __init__(self, transport: GeoapifyRouteTransport) -> None:
        self._transport = transport

    @property
    def cache_namespace(self) -> str:
        return GEOAPIFY_ROUTES_CACHE_NAMESPACE

    async def route(self, request: RouteRequest) -> RouteResult:
        result = await self._transport.route(
            GeoapifyRouteQuery(
                origin=request.origin.coordinates,
                destination=request.destination.coordinates,
                avoid_tolls=request.options.avoid_tolls,
                avoid_highways=request.options.avoid_highways,
                depart_at=request.depart_at,
            )
        )
        if isinstance(result, GeoapifyRouteFailure):
            return RouteFailure(result.category, GEOAPIFY_PROVIDER, result.occurred_at)
        return RouteSuccess(
            Route(
                origin=request.origin,
                destination=request.destination,
                distance_m=result.distance_m,
                duration_s=result.duration_s,
                provider=GEOAPIFY_PROVIDER,
                observed_at=result.observed_at,
                quality=DataQuality.COMPLETE,
            )
        )


class GeoapifyGeocoder:
    """Persistent-cache and request-budget boundary for Geoapify geocoding."""

    def __init__(
        self,
        *,
        api_key: str,
        transport: GeoapifyGeocodeTransport,
        cache: GeocodeCache,
        config: ProfileRouteConfig,
        budget: ProviderRefreshBudget,
        privacy_key: bytes,
        now: Callable[[], datetime],
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._cache = cache
        self._config = config
        self._budget = budget
        self._privacy_key = privacy_key
        self._now = now

    @property
    def cache_namespace(self) -> str:
        return GEOAPIFY_GEOCODING_CACHE_NAMESPACE

    async def resolve(self, request: EventLocationRequest) -> EventLocationResult:
        evaluated_at = self._current_time()
        key: GeocodeCacheKey = build_geocode_cache_key(
            request.location_text,
            privacy_key=self._privacy_key,
            provider_namespace=self.cache_namespace,
        )
        entry = await self._cache.get(key)
        if entry is not None:
            age = evaluated_at - entry.stored_at
            if age.total_seconds() < 0:
                raise ValueError("current time must not precede cache insertion")
            if age <= self._config.geocode_cache_policy.maximum_age:
                return EventLocationSuccess(entry.coordinates)
            await self._cache.delete(key)

        attempts = 0
        while True:
            if not self._budget.start_geocode():
                return EventLocationFailure(
                    EventLocationFailureCategory.QUOTA_EXCEEDED,
                    self._current_time(),
                )
            attempts += 1
            result = await self._call_transport(request)
            if isinstance(result, GeoapifyGeocodeResponse):
                await self._cache.put(key, result.coordinates, self._current_time())
                return EventLocationSuccess(result.coordinates)
            failure = EventLocationFailure(result.category, result.occurred_at)
            if not self._config.request_policy.can_retry(
                failed_attempt=attempts, retryable=result.retryable
            ):
                return failure

    async def _call_transport(
        self, request: EventLocationRequest
    ) -> GeoapifyGeocodeTransportResult:
        try:
            return await asyncio.wait_for(
                self._transport.geocode(
                    GeoapifyGeocodeQuery(self._api_key, request.location_text)
                ),
                timeout=self._config.request_policy.timeout.total_seconds(),
            )
        except TimeoutError:
            return GeoapifyGeocodeFailure(
                EventLocationFailureCategory.TRANSIENT,
                self._current_time(),
            )

    def _current_time(self) -> datetime:
        value = self._now()
        _require_aware(value, "current time")
        return value


class _BoundedGeoapifyRouteAdapter(GeoapifyRouteAdapter):
    def __init__(
        self,
        transport: GeoapifyRouteTransport,
        *,
        config: ProfileRouteConfig,
        budget: ProviderRefreshBudget,
        now: Callable[[], datetime],
    ) -> None:
        super().__init__(transport)
        self._config = config
        self._budget = budget
        self._now = now

    async def route(self, request: RouteRequest) -> RouteResult:
        attempts = 0
        while True:
            if not self._budget.start_route():
                return RouteFailure(
                    RouteFailureCategory.QUOTA_EXCEEDED,
                    GEOAPIFY_PROVIDER,
                    self._current_time(),
                )
            attempts += 1
            try:
                result = await asyncio.wait_for(
                    super().route(request),
                    timeout=self._config.request_policy.timeout.total_seconds(),
                )
            except TimeoutError:
                result = RouteFailure(
                    RouteFailureCategory.TRANSIENT,
                    GEOAPIFY_PROVIDER,
                    self._current_time(),
                )
            if not isinstance(result, RouteFailure):
                return result
            if not self._config.request_policy.can_retry(
                failed_attempt=attempts,
                retryable=result.category
                in (RouteFailureCategory.RATE_LIMITED, RouteFailureCategory.TRANSIENT),
            ):
                return result

    def _current_time(self) -> datetime:
        value = self._now()
        _require_aware(value, "current time")
        return value


class GeoapifyRouter:
    """Persistent directional route cache around bounded Geoapify calls."""

    def __init__(
        self,
        *,
        provider: GeoapifyRouteAdapter,
        cache: RouteCache,
        config: ProfileRouteConfig,
        privacy_key: bytes,
        now: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._config = config
        self._privacy_key = privacy_key
        self._now = now

    @property
    def cache_namespace(self) -> str:
        return self._provider.cache_namespace

    async def route(self, request: RouteRequest) -> RouteResult:
        evaluated_at = self._now()
        _require_aware(evaluated_at, "current time")
        return await route_with_cache(
            request=request,
            provider=self._provider,
            cache=self._cache,
            policy=self._config.route_cache_policy,
            privacy_key=self._privacy_key,
            evaluated_at=evaluated_at,
        )


@dataclass(frozen=True, slots=True)
class GeoapifyAdapters:
    """One selected Geoapify geocoder/router and shared refresh budget."""

    geocoder: GeoapifyGeocoder = field(repr=False)
    router: GeoapifyRouter = field(repr=False)
    budget: ProviderRefreshBudget


def build_geoapify_adapters(
    *,
    config: ProfileRouteConfig,
    geocode_transport: GeoapifyGeocodeTransport,
    route_transport: GeoapifyRouteTransport,
    geocode_cache: GeocodeCache,
    route_cache: RouteCache,
    privacy_key: bytes,
    now: Callable[[], datetime],
) -> GeoapifyAdapters:
    """Build Geoapify only when explicitly selected, without fallback."""

    if config.provider is not RouteProviderKind.GEOAPIFY or config.api_key is None:
        raise ValueError("selected provider is not Geoapify")
    budget = ProviderRefreshBudget(config.request_policy)
    geocoder = GeoapifyGeocoder(
        api_key=config.api_key,
        transport=geocode_transport,
        cache=geocode_cache,
        config=config,
        budget=budget,
        privacy_key=privacy_key,
        now=now,
    )
    provider = _BoundedGeoapifyRouteAdapter(
        route_transport,
        config=config,
        budget=budget,
        now=now,
    )
    return GeoapifyAdapters(
        geocoder=geocoder,
        router=GeoapifyRouter(
            provider=provider,
            cache=route_cache,
            config=config,
            privacy_key=privacy_key,
            now=now,
        ),
        budget=budget,
    )
