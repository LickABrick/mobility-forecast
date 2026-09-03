"""Injected OpenRouteService adapters with bounded, cache-aware execution.

This module deliberately contains no HTTP implementation. A caller must inject
transports which understand the selected hosted or self-hosted endpoint contract.
Private locations, coordinates, credentials, and configured endpoints are omitted
from representations.
"""

from __future__ import annotations

import asyncio
import hashlib
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
    RouteProvider,
    RouteRequest,
    RouteResult,
    RouteSuccess,
    route_with_cache,
)
from .provider_guardrails import (
    GeocodeCacheKey,
    ProviderRequestPolicy,
    build_geocode_cache_key,
)
from .route_provider_config import (
    ORS_HOSTED_GEOCODING_ENDPOINT,
    ORS_HOSTED_ROUTING_ENDPOINT,
    GeocoderKind,
    ProfileRouteConfig,
    RouteProviderKind,
)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _private_namespace(*, role: str, variant: str, endpoint: str) -> str:
    endpoint_digest = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]
    return f"openrouteservice:{role}:{variant}:{endpoint_digest}:v1"


@dataclass(frozen=True, slots=True)
class OpenRouteServiceGeocodeQuery:
    """Minimal geocoder query delivered only to an injected transport."""

    endpoint: str = field(repr=False)
    api_key: str | None = field(repr=False)
    geocoder: GeocoderKind
    location_text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.endpoint.strip():
            raise ValueError("geocoding endpoint must not be empty")
        if not self.location_text.strip():
            raise ValueError("location text must not be empty")
        if self.api_key is not None and not self.api_key.strip():
            raise ValueError("API key must not be empty")


@dataclass(frozen=True, slots=True)
class OpenRouteServiceGeocodeResponse:
    """Validated provider-independent coordinates from a synthetic transport."""

    coordinates: Coordinates = field(repr=False)


@dataclass(frozen=True, slots=True)
class OpenRouteServiceGeocodeFailure:
    """Sanitized geocoder failure without provider response or request data."""

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


type OpenRouteServiceGeocodeTransportResult = (
    OpenRouteServiceGeocodeResponse | OpenRouteServiceGeocodeFailure
)


class OpenRouteServiceGeocodeTransport(Protocol):
    """Injected geocoding I/O boundary; no implementation is provided here."""

    async def geocode(
        self, query: OpenRouteServiceGeocodeQuery
    ) -> OpenRouteServiceGeocodeTransportResult:
        """Return validated synthetic/provider-decoded data."""
        ...


@dataclass(frozen=True, slots=True)
class OpenRouteServiceRouteQuery:
    """Minimal routing query delivered only to an injected transport."""

    endpoint: str = field(repr=False)
    api_key: str | None = field(repr=False)
    origin: Coordinates = field(repr=False)
    destination: Coordinates = field(repr=False)
    avoid_tolls: bool
    avoid_highways: bool
    depart_at: datetime | None

    def __post_init__(self) -> None:
        if not self.endpoint.strip():
            raise ValueError("routing endpoint must not be empty")
        if self.api_key is not None and not self.api_key.strip():
            raise ValueError("API key must not be empty")
        if self.origin == self.destination:
            raise ValueError("origin and destination coordinates must differ")
        if self.depart_at is not None:
            _require_aware(self.depart_at, "depart_at")


@dataclass(frozen=True, slots=True)
class OpenRouteServiceRouteResponse:
    """Validated route values independent from an HTTP response shape."""

    distance_m: int
    duration_s: int
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_positive_int(self.distance_m, "distance_m")
        _require_positive_int(self.duration_s, "duration_s")
        _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class OpenRouteServiceRouteFailure:
    """Sanitized routing failure without provider response or endpoint data."""

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


type OpenRouteServiceRouteTransportResult = (
    OpenRouteServiceRouteResponse | OpenRouteServiceRouteFailure
)


class OpenRouteServiceRouteTransport(Protocol):
    """Injected routing I/O boundary; no implementation is provided here."""

    async def route(
        self, query: OpenRouteServiceRouteQuery
    ) -> OpenRouteServiceRouteTransportResult:
        """Return validated synthetic/provider-decoded data."""
        ...


@dataclass(frozen=True, slots=True)
class GeocodeCacheEntry:
    """Successful geocode and local insertion time, with hidden coordinates."""

    coordinates: Coordinates = field(repr=False)
    stored_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.stored_at, "stored_at")


class GeocodeCache(Protocol):
    """Profile-owned cache that stores only opaque keys and coordinates."""

    async def get(self, key: GeocodeCacheKey) -> GeocodeCacheEntry | None:
        """Read an entry without applying its configured retention."""
        ...

    async def put(
        self, key: GeocodeCacheKey, coordinates: Coordinates, stored_at: datetime
    ) -> None:
        """Store a successful result under an opaque profile-scoped key."""
        ...

    async def delete(self, key: GeocodeCacheKey) -> None:
        """Remove an entry once its configured retention expires."""
        ...


class InMemoryGeocodeCache:
    """Deterministic cache fake retaining no raw location text."""

    def __init__(self) -> None:
        self._entries: dict[GeocodeCacheKey, GeocodeCacheEntry] = {}

    async def get(self, key: GeocodeCacheKey) -> GeocodeCacheEntry | None:
        return self._entries.get(key)

    async def put(
        self, key: GeocodeCacheKey, coordinates: Coordinates, stored_at: datetime
    ) -> None:
        self._entries[key] = GeocodeCacheEntry(coordinates, stored_at)

    async def delete(self, key: GeocodeCacheKey) -> None:
        self._entries.pop(key, None)


class ProviderRefreshBudget:
    """One shared mutable attempt budget scoped to exactly one refresh."""

    def __init__(self, policy: ProviderRequestPolicy) -> None:
        self._policy = policy
        self._geocode_requests = 0
        self._route_requests = 0

    @property
    def geocode_requests(self) -> int:
        return self._geocode_requests

    @property
    def route_requests(self) -> int:
        return self._route_requests

    def start_geocode(self) -> bool:
        if not self._policy.can_start_geocode(
            completed_requests=self._geocode_requests
        ):
            return False
        self._geocode_requests += 1
        return True

    def start_route(self) -> bool:
        if not self._policy.can_start_route(completed_requests=self._route_requests):
            return False
        self._route_requests += 1
        return True


class OpenRouteServiceGeocoder:
    """Cache-aware and budgeted event-location adapter for one selected endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None,
        geocoder: GeocoderKind,
        transport: OpenRouteServiceGeocodeTransport,
        cache: GeocodeCache,
        cache_namespace: str,
        config: ProfileRouteConfig,
        budget: ProviderRefreshBudget,
        privacy_key: bytes,
        now: Callable[[], datetime],
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._geocoder = geocoder
        self._transport = transport
        self._cache = cache
        self._cache_namespace = cache_namespace
        self._config = config
        self._budget = budget
        self._privacy_key = privacy_key
        self._now = now

    @property
    def cache_namespace(self) -> str:
        return self._cache_namespace

    async def resolve(self, request: EventLocationRequest) -> EventLocationResult:
        evaluated_at = self._current_time()
        key = build_geocode_cache_key(
            request.location_text,
            privacy_key=self._privacy_key,
            provider_namespace=self._cache_namespace,
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
            if isinstance(result, OpenRouteServiceGeocodeResponse):
                await self._cache.put(key, result.coordinates, self._current_time())
                return EventLocationSuccess(result.coordinates)
            failure = EventLocationFailure(result.category, result.occurred_at)
            if not self._config.request_policy.can_retry(
                failed_attempt=attempts, retryable=result.retryable
            ):
                return failure

    async def _call_transport(
        self, request: EventLocationRequest
    ) -> OpenRouteServiceGeocodeTransportResult:
        query = OpenRouteServiceGeocodeQuery(
            endpoint=self._endpoint,
            api_key=self._api_key,
            geocoder=self._geocoder,
            location_text=request.location_text,
        )
        try:
            return await asyncio.wait_for(
                self._transport.geocode(query),
                timeout=self._config.request_policy.timeout.total_seconds(),
            )
        except TimeoutError:
            return OpenRouteServiceGeocodeFailure(
                EventLocationFailureCategory.TRANSIENT,
                self._current_time(),
            )

    def _current_time(self) -> datetime:
        value = self._now()
        _require_aware(value, "current time")
        return value


class _OpenRouteServiceTransportProvider:
    """Budgeted transport adapter used behind the configured route cache."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None,
        provider_name: str,
        cache_namespace: str,
        transport: OpenRouteServiceRouteTransport,
        config: ProfileRouteConfig,
        budget: ProviderRefreshBudget,
        now: Callable[[], datetime],
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._provider_name = provider_name
        self._cache_namespace = cache_namespace
        self._transport = transport
        self._config = config
        self._budget = budget
        self._now = now

    @property
    def cache_namespace(self) -> str:
        return self._cache_namespace

    async def route(self, request: RouteRequest) -> RouteResult:
        attempts = 0
        while True:
            if not self._budget.start_route():
                return RouteFailure(
                    RouteFailureCategory.QUOTA_EXCEEDED,
                    self._provider_name,
                    self._current_time(),
                )
            attempts += 1
            result = await self._call_transport(request)
            if isinstance(result, OpenRouteServiceRouteResponse):
                return RouteSuccess(
                    Route(
                        origin=request.origin,
                        destination=request.destination,
                        distance_m=result.distance_m,
                        duration_s=result.duration_s,
                        provider=self._provider_name,
                        observed_at=result.observed_at,
                        quality=DataQuality.COMPLETE,
                    )
                )
            failure = RouteFailure(
                result.category,
                self._provider_name,
                result.occurred_at,
            )
            if not self._config.request_policy.can_retry(
                failed_attempt=attempts, retryable=result.retryable
            ):
                return failure

    async def _call_transport(
        self, request: RouteRequest
    ) -> OpenRouteServiceRouteTransportResult:
        query = OpenRouteServiceRouteQuery(
            endpoint=self._endpoint,
            api_key=self._api_key,
            origin=request.origin.coordinates,
            destination=request.destination.coordinates,
            avoid_tolls=request.options.avoid_tolls,
            avoid_highways=request.options.avoid_highways,
            depart_at=request.depart_at,
        )
        try:
            return await asyncio.wait_for(
                self._transport.route(query),
                timeout=self._config.request_policy.timeout.total_seconds(),
            )
        except TimeoutError:
            return OpenRouteServiceRouteFailure(
                RouteFailureCategory.TRANSIENT,
                self._current_time(),
            )

    def _current_time(self) -> datetime:
        value = self._now()
        _require_aware(value, "current time")
        return value


class OpenRouteServiceRouter:
    """Configured route-cache boundary around one ORS transport provider."""

    def __init__(
        self,
        *,
        provider: RouteProvider,
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
class OpenRouteServiceAdapters:
    """One provider selection and one shared per-refresh request budget."""

    geocoder: OpenRouteServiceGeocoder = field(repr=False)
    router: OpenRouteServiceRouter = field(repr=False)
    budget: ProviderRefreshBudget


def build_openrouteservice_adapters(
    *,
    config: ProfileRouteConfig,
    geocode_transport: OpenRouteServiceGeocodeTransport,
    route_transport: OpenRouteServiceRouteTransport,
    geocode_cache: GeocodeCache,
    route_cache: RouteCache,
    privacy_key: bytes,
    now: Callable[[], datetime],
) -> OpenRouteServiceAdapters:
    """Build only the explicitly selected ORS mode; never choose or fall back."""

    if config.provider is RouteProviderKind.OPENROUTESERVICE_HOSTED:
        geocode_endpoint = ORS_HOSTED_GEOCODING_ENDPOINT
        route_endpoint = ORS_HOSTED_ROUTING_ENDPOINT
        geocoder = GeocoderKind.PELIAS
        provider_name = RouteProviderKind.OPENROUTESERVICE_HOSTED.value
        variant = "hosted"
    elif config.provider is RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED:
        if (
            config.geocoder is None
            or config.geocoder_base_url is None
            or config.routing_base_url is None
        ):
            raise ValueError("self-hosted OpenRouteService configuration is incomplete")
        geocode_endpoint = config.geocoder_base_url
        route_endpoint = config.routing_base_url
        geocoder = config.geocoder
        provider_name = RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED.value
        variant = f"self-hosted-{geocoder.value}"
    else:
        raise ValueError("selected provider is not OpenRouteService")

    budget = ProviderRefreshBudget(config.request_policy)
    geocode_namespace = _private_namespace(
        role="geocode", variant=variant, endpoint=geocode_endpoint
    )
    route_namespace = _private_namespace(
        role="route", variant=variant, endpoint=route_endpoint
    )
    geocode_adapter = OpenRouteServiceGeocoder(
        endpoint=geocode_endpoint,
        api_key=config.api_key,
        geocoder=geocoder,
        transport=geocode_transport,
        cache=geocode_cache,
        cache_namespace=geocode_namespace,
        config=config,
        budget=budget,
        privacy_key=privacy_key,
        now=now,
    )
    transport_provider = _OpenRouteServiceTransportProvider(
        endpoint=route_endpoint,
        api_key=config.api_key,
        provider_name=provider_name,
        cache_namespace=route_namespace,
        transport=route_transport,
        config=config,
        budget=budget,
        now=now,
    )
    route_adapter = OpenRouteServiceRouter(
        provider=transport_provider,
        cache=route_cache,
        config=config,
        privacy_key=privacy_key,
        now=now,
    )
    return OpenRouteServiceAdapters(geocode_adapter, route_adapter, budget)
