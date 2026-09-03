"""Bounded, cache-aware Google Geocoding and Routes adapters."""

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

GOOGLE_ROUTES_PROVIDER = "google_routes"
GOOGLE_ROUTES_CACHE_NAMESPACE = "google_routes:v1"
GOOGLE_GEOCODING_CACHE_NAMESPACE = "google_geocoding:v1"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class GoogleGeocodeQuery:
    """Private address query delivered only to the Google HTTP transport."""

    api_key: str = field(repr=False)
    location_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("API key must not be empty")
        if not self.location_text.strip():
            raise ValueError("location text must not be empty")


@dataclass(frozen=True, slots=True)
class GoogleGeocodeResponse:
    """Validated Google geocode coordinates hidden from representations."""

    coordinates: Coordinates = field(repr=False)


@dataclass(frozen=True, slots=True)
class GoogleGeocodeFailure:
    """Sanitized Google geocoding failure."""

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


type GoogleGeocodeTransportResult = GoogleGeocodeResponse | GoogleGeocodeFailure


class GoogleGeocodeTransport(Protocol):
    """Injected Google Geocoding I/O boundary."""

    async def geocode(self, query: GoogleGeocodeQuery) -> GoogleGeocodeTransportResult:
        """Return validated coordinates or a sanitized failure."""
        ...


@dataclass(frozen=True, slots=True)
class GoogleRoutesQuery:
    """Minimal provider query; private coordinates stay out of representations."""

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
class GoogleRoutesResponse:
    """Validated transport success independent from an HTTP response shape."""

    distance_m: int
    duration_s: int
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_positive_int(self.distance_m, "distance_m")
        _require_positive_int(self.duration_s, "duration_s")
        _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class GoogleRoutesFailure:
    """Sanitized transport failure with no response text or request data."""

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


type GoogleRoutesTransportResult = GoogleRoutesResponse | GoogleRoutesFailure


class GoogleRoutesTransport(Protocol):
    """Injected I/O boundary; unattended tests supply only an in-memory fake."""

    async def compute_route(
        self, query: GoogleRoutesQuery
    ) -> GoogleRoutesTransportResult:
        """Return a validated success or privacy-safe failure."""
        ...


class GoogleRoutesAdapter:
    """Translate provider-neutral routes to a transport contract and back."""

    def __init__(self, transport: GoogleRoutesTransport) -> None:
        self._transport = transport

    @property
    def cache_namespace(self) -> str:
        return GOOGLE_ROUTES_CACHE_NAMESPACE

    async def route(self, request: RouteRequest) -> RouteResult:
        result = await self._transport.compute_route(
            GoogleRoutesQuery(
                origin=request.origin.coordinates,
                destination=request.destination.coordinates,
                avoid_tolls=request.options.avoid_tolls,
                avoid_highways=request.options.avoid_highways,
                depart_at=request.depart_at,
            )
        )
        if isinstance(result, GoogleRoutesFailure):
            return RouteFailure(
                category=result.category,
                provider=GOOGLE_ROUTES_PROVIDER,
                occurred_at=result.occurred_at,
            )
        return RouteSuccess(
            Route(
                origin=request.origin,
                destination=request.destination,
                distance_m=result.distance_m,
                duration_s=result.duration_s,
                provider=GOOGLE_ROUTES_PROVIDER,
                observed_at=result.observed_at,
                quality=DataQuality.COMPLETE,
            )
        )


class GoogleGeocoder:
    """Persistent-cache and request-budget boundary for Google Geocoding."""

    def __init__(
        self,
        *,
        api_key: str,
        transport: GoogleGeocodeTransport,
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

    async def resolve(self, request: EventLocationRequest) -> EventLocationResult:
        evaluated_at = self._current_time()
        key: GeocodeCacheKey = build_geocode_cache_key(
            request.location_text,
            privacy_key=self._privacy_key,
            provider_namespace=GOOGLE_GEOCODING_CACHE_NAMESPACE,
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
            try:
                result = await asyncio.wait_for(
                    self._transport.geocode(
                        GoogleGeocodeQuery(self._api_key, request.location_text)
                    ),
                    timeout=self._config.request_policy.timeout.total_seconds(),
                )
            except TimeoutError:
                result = GoogleGeocodeFailure(
                    EventLocationFailureCategory.TRANSIENT,
                    self._current_time(),
                )
            if isinstance(result, GoogleGeocodeResponse):
                await self._cache.put(key, result.coordinates, self._current_time())
                return EventLocationSuccess(result.coordinates)
            failure = EventLocationFailure(result.category, result.occurred_at)
            if not self._config.request_policy.can_retry(
                failed_attempt=attempts, retryable=result.retryable
            ):
                return failure

    def _current_time(self) -> datetime:
        value = self._now()
        _require_aware(value, "current time")
        return value


class _BoundedGoogleRoutesAdapter(GoogleRoutesAdapter):
    def __init__(
        self,
        transport: GoogleRoutesTransport,
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
                    GOOGLE_ROUTES_PROVIDER,
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
                    GOOGLE_ROUTES_PROVIDER,
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


class GoogleRouter:
    """Persistent directional route cache around bounded Google Routes calls."""

    def __init__(
        self,
        *,
        provider: GoogleRoutesAdapter,
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
class GoogleAdapters:
    """One selected Google geocoder/router and shared refresh budget."""

    geocoder: GoogleGeocoder = field(repr=False)
    router: GoogleRouter = field(repr=False)
    budget: ProviderRefreshBudget


def build_google_adapters(
    *,
    config: ProfileRouteConfig,
    geocode_transport: GoogleGeocodeTransport,
    route_transport: GoogleRoutesTransport,
    geocode_cache: GeocodeCache,
    route_cache: RouteCache,
    privacy_key: bytes,
    now: Callable[[], datetime],
) -> GoogleAdapters:
    """Build Google only when explicitly selected, without fallback."""

    if config.provider is not RouteProviderKind.GOOGLE or config.api_key is None:
        raise ValueError("selected provider is not Google")
    budget = ProviderRefreshBudget(config.request_policy)
    geocoder = GoogleGeocoder(
        api_key=config.api_key,
        transport=geocode_transport,
        cache=geocode_cache,
        config=config,
        budget=budget,
        privacy_key=privacy_key,
        now=now,
    )
    provider = _BoundedGoogleRoutesAdapter(
        route_transport,
        config=config,
        budget=budget,
        now=now,
    )
    return GoogleAdapters(
        geocoder=geocoder,
        router=GoogleRouter(
            provider=provider,
            cache=route_cache,
            config=config,
            privacy_key=privacy_key,
            now=now,
        ),
        budget=budget,
    )
