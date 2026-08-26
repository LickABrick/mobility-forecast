"""Provider-neutral directional routing and privacy-safe cache behavior."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol, TypeAlias

from .models import DataQuality, Route, ResolvedLocation


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class RouteOptions:
    """Provider-neutral options that affect route selection."""

    avoid_tolls: bool
    avoid_highways: bool


@dataclass(frozen=True, slots=True)
class RouteRequest:
    """Directional route input with private endpoints hidden from representations."""

    origin: ResolvedLocation = field(repr=False)
    destination: ResolvedLocation = field(repr=False)
    options: RouteOptions
    depart_at: datetime | None

    def __post_init__(self) -> None:
        if self.origin.coordinates == self.destination.coordinates:
            raise ValueError("origin and destination coordinates must differ")
        if self.depart_at is not None:
            _require_aware(self.depart_at, "depart_at")


class RouteFailureCategory(StrEnum):
    """Stable, provider-neutral failure categories."""

    INVALID_INPUT = "invalid_input"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    TRANSIENT = "transient"


class RouteResultSource(StrEnum):
    """Where a successful result was obtained."""

    PROVIDER = "provider"
    CACHE = "cache"
    STALE_CACHE = "stale_cache"


@dataclass(frozen=True, slots=True)
class RouteFailure:
    """Privacy-safe route failure without provider response text or endpoint data."""

    category: RouteFailureCategory
    provider: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _require_non_empty(self.provider, "provider")
        _require_aware(self.occurred_at, "occurred_at")

    @property
    def retryable(self) -> bool:
        return self.category in (
            RouteFailureCategory.RATE_LIMITED,
            RouteFailureCategory.TRANSIENT,
        )


@dataclass(frozen=True, slots=True)
class RouteSuccess:
    """Successful current or stale route with cache-refresh context."""

    route: Route
    source: RouteResultSource = RouteResultSource.PROVIDER
    refresh_failure: RouteFailureCategory | None = None

    def __post_init__(self) -> None:
        if self.source is RouteResultSource.STALE_CACHE:
            if self.route.quality is not DataQuality.STALE:
                raise ValueError("stale-cache result must have stale route quality")
            if self.refresh_failure is None:
                raise ValueError("stale-cache result must retain refresh failure")
        elif self.refresh_failure is not None:
            raise ValueError("refresh failure is valid only for stale-cache results")


RouteResult: TypeAlias = RouteSuccess | RouteFailure


class RouteProvider(Protocol):
    """Asynchronous provider boundary; adapters expose no provider-specific types."""

    @property
    def cache_namespace(self) -> str:
        """Return a stable non-secret identity for route-affecting provider config."""
        ...

    async def route(self, request: RouteRequest) -> RouteResult:
        """Calculate one directional route."""
        ...


@dataclass(frozen=True, slots=True)
class RouteCacheKey:
    """Opaque profile-scoped digest; raw endpoints are never retained."""

    digest: str

    def __post_init__(self) -> None:
        if len(self.digest) != hashlib.sha256().digest_size * 2:
            raise ValueError("digest must be a SHA-256 hexadecimal digest")
        try:
            bytes.fromhex(self.digest)
        except ValueError as error:
            raise ValueError("digest must be hexadecimal") from error


@dataclass(frozen=True, slots=True)
class RouteCachePolicy:
    """Required inclusive age limits; no product default is implied."""

    maximum_fresh_age: timedelta
    maximum_stale_age: timedelta

    def __post_init__(self) -> None:
        if self.maximum_fresh_age <= timedelta(0):
            raise ValueError("maximum_fresh_age must be positive")
        if self.maximum_stale_age < self.maximum_fresh_age:
            raise ValueError("maximum_stale_age must be at least maximum_fresh_age")


@dataclass(frozen=True, slots=True)
class RouteCacheEntry:
    """Successful route and local insertion time."""

    route: Route
    stored_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.stored_at, "stored_at")
        if self.route.quality is not DataQuality.COMPLETE:
            raise ValueError("only complete provider routes may be cached")


class RouteCache(Protocol):
    """Minimal profile-owned cache storage boundary."""

    async def get(self, key: RouteCacheKey) -> RouteCacheEntry | None:
        """Return the matching entry without applying age policy."""
        ...

    async def put(
        self,
        key: RouteCacheKey,
        route: Route,
        stored_at: datetime,
    ) -> None:
        """Store a successful current route."""
        ...


def build_route_cache_key(
    request: RouteRequest,
    privacy_key: bytes,
    provider_namespace: str,
) -> RouteCacheKey:
    """HMAC every route-affecting input with profile-local key material."""

    if len(privacy_key) < 16:
        raise ValueError("privacy_key must contain at least 16 bytes")
    _require_non_empty(provider_namespace, "provider_namespace")
    origin = request.origin.coordinates
    destination = request.destination.coordinates
    departure = (
        request.depart_at.isoformat() if request.depart_at is not None else "none"
    )
    canonical = "\x1f".join(
        (
            provider_namespace,
            origin.latitude.hex(),
            origin.longitude.hex(),
            destination.latitude.hex(),
            destination.longitude.hex(),
            departure,
            "1" if request.options.avoid_tolls else "0",
            "1" if request.options.avoid_highways else "0",
        )
    ).encode()
    return RouteCacheKey(hmac.new(privacy_key, canonical, hashlib.sha256).hexdigest())


class DeterministicRouteProvider:
    """Exact in-memory fake that cannot perform network access."""

    def __init__(
        self,
        cache_namespace: str,
        responses: dict[RouteRequest, RouteResult],
    ) -> None:
        _require_non_empty(cache_namespace, "cache_namespace")
        self._cache_namespace = cache_namespace
        self._responses = dict(responses)
        self._requests: list[RouteRequest] = []

    @property
    def cache_namespace(self) -> str:
        return self._cache_namespace

    @property
    def requests(self) -> tuple[RouteRequest, ...]:
        return tuple(self._requests)

    async def route(self, request: RouteRequest) -> RouteResult:
        self._requests.append(request)
        try:
            return self._responses[request]
        except KeyError as error:
            raise AssertionError(
                "unexpected route request to deterministic fake"
            ) from error


class InMemoryRouteCache:
    """Deterministic profile-local cache fake."""

    def __init__(self) -> None:
        self._entries: dict[RouteCacheKey, RouteCacheEntry] = {}

    async def get(self, key: RouteCacheKey) -> RouteCacheEntry | None:
        return self._entries.get(key)

    async def put(
        self,
        key: RouteCacheKey,
        route: Route,
        stored_at: datetime,
    ) -> None:
        self._entries[key] = RouteCacheEntry(route, stored_at)


def _validate_route_direction(request: RouteRequest, route: Route) -> None:
    if route.origin != request.origin or route.destination != request.destination:
        raise ValueError("route direction does not match request")


def _validate_provider_success(request: RouteRequest, success: RouteSuccess) -> None:
    if success.source is not RouteResultSource.PROVIDER:
        raise ValueError("provider must return provider-sourced success")
    _validate_route_direction(request, success.route)
    if success.route.quality is not DataQuality.COMPLETE:
        raise ValueError("provider success must have complete route quality")


async def route_with_cache(
    *,
    request: RouteRequest,
    provider: RouteProvider,
    cache: RouteCache,
    policy: RouteCachePolicy,
    privacy_key: bytes,
    evaluated_at: datetime,
) -> RouteResult:
    """Use fresh cache, refresh stale cache, and preserve explicit failures."""

    _require_aware(evaluated_at, "evaluated_at")
    key = build_route_cache_key(request, privacy_key, provider.cache_namespace)
    entry = await cache.get(key)
    stale_entry: RouteCacheEntry | None = None
    if entry is not None:
        _validate_route_direction(request, entry.route)
        age = evaluated_at - entry.stored_at
        if age < timedelta(0):
            raise ValueError("evaluated_at must not precede cache insertion")
        if age <= policy.maximum_fresh_age:
            return RouteSuccess(entry.route, RouteResultSource.CACHE)
        if age <= policy.maximum_stale_age:
            stale_entry = entry

    result = await provider.route(request)
    if isinstance(result, RouteSuccess):
        _validate_provider_success(request, result)
        await cache.put(key, result.route, evaluated_at)
        return result
    if stale_entry is not None:
        stale_route = replace(stale_entry.route, quality=DataQuality.STALE)
        return RouteSuccess(
            stale_route,
            RouteResultSource.STALE_CACHE,
            result.category,
        )
    return result
