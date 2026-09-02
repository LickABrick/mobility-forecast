"""Google Routes adapter over an injected transport with no network implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .domain.models import Coordinates, DataQuality, Route
from .domain.routing import (
    RouteFailure,
    RouteFailureCategory,
    RouteRequest,
    RouteResult,
    RouteSuccess,
)

GOOGLE_ROUTES_PROVIDER = "google_routes"
GOOGLE_ROUTES_CACHE_NAMESPACE = "google_routes:v1"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_positive_int(value: int, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


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
