"""Synthetic-testable Geoapify geocoding and routing HTTP shaping.

The transports stop at the shared injected HTTP sender. They make no direct network
calls and keep URLs, credentials, location text, coordinates and bodies out of
representations.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime
from typing import Protocol, cast

from .domain.event_locations import EventLocationFailureCategory
from .domain.models import Coordinates
from .domain.routing import RouteFailureCategory
from .geoapify import (
    GeoapifyGeocodeFailure,
    GeoapifyGeocodeQuery,
    GeoapifyGeocodeResponse,
    GeoapifyGeocodeTransportResult,
    GeoapifyRouteFailure,
    GeoapifyRouteQuery,
    GeoapifyRouteResponse,
    GeoapifyRouteTransportResult,
)
from .openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResult,
)
from .route_provider_config import (
    GEOAPIFY_GEOCODING_ENDPOINT,
    GEOAPIFY_ROUTING_ENDPOINT,
)


class _MalformedResponseError(ValueError):
    """Internal marker for an invalid provider success payload."""


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("current time must be timezone-aware")
    return value


def _require_key(api_key: str) -> str:
    if not api_key.strip():
        raise ValueError("API key must not be empty")
    return api_key


def _headers() -> tuple[tuple[str, str], ...]:
    return (("Accept", "application/json"),)


def _geocode_request(query: GeoapifyGeocodeQuery) -> InjectedHttpRequest:
    return InjectedHttpRequest(
        method="GET",
        url=GEOAPIFY_GEOCODING_ENDPOINT,
        headers=_headers(),
        query=(
            ("text", query.location_text),
            ("limit", "1"),
            ("format", "geojson"),
            ("apiKey", query.api_key),
        ),
        json_body=None,
    )


def _coordinate_text(coordinates: Coordinates) -> str:
    return f"{coordinates.latitude},{coordinates.longitude}"


def _route_request(query: GeoapifyRouteQuery, api_key: str) -> InjectedHttpRequest:
    parameters: list[tuple[str, str]] = [
        (
            "waypoints",
            f"{_coordinate_text(query.origin)}|{_coordinate_text(query.destination)}",
        ),
        ("mode", "drive"),
        ("units", "metric"),
    ]
    avoid: list[str] = []
    if query.avoid_tolls:
        avoid.append("tolls")
    if query.avoid_highways:
        avoid.append("highways")
    if avoid:
        parameters.append(("avoid", "|".join(avoid)))
    parameters.extend((("format", "geojson"), ("apiKey", api_key)))
    return InjectedHttpRequest(
        method="GET",
        url=GEOAPIFY_ROUTING_ENDPOINT,
        headers=_headers(),
        query=tuple(parameters),
        json_body=None,
    )


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _MalformedResponseError
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        raise _MalformedResponseError
    return cast(dict[str, object], mapping)


def _sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise _MalformedResponseError
    return cast(list[object], value)


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _MalformedResponseError
    number = float(value)
    if not math.isfinite(number):
        raise _MalformedResponseError
    return number


def _coordinate(longitude: object, latitude: object) -> Coordinates:
    try:
        return Coordinates(
            latitude=_finite_number(latitude),
            longitude=_finite_number(longitude),
        )
    except ValueError as error:
        raise _MalformedResponseError from error


def _positive_ceiling(value: object) -> int:
    number = _finite_number(value)
    if number <= 0:
        raise _MalformedResponseError
    return math.ceil(number)


def _decode_geocode(body: object) -> Coordinates | None:
    features = _sequence(_mapping(body).get("features"))
    if not features:
        return None
    geometry = _mapping(_mapping(features[0]).get("geometry"))
    if geometry.get("type") != "Point":
        raise _MalformedResponseError
    coordinates = _sequence(geometry.get("coordinates"))
    if len(coordinates) != 2:
        raise _MalformedResponseError
    return _coordinate(coordinates[0], coordinates[1])


def _decode_route(body: object) -> tuple[int, int]:
    features = _sequence(_mapping(body).get("features"))
    if not features:
        raise _MalformedResponseError
    properties = _mapping(_mapping(features[0]).get("properties"))
    return (
        _positive_ceiling(properties.get("distance")),
        _positive_ceiling(properties.get("time")),
    )


def _geocode_status_category(status_code: int) -> EventLocationFailureCategory:
    if status_code == 400:
        return EventLocationFailureCategory.INVALID_INPUT
    if status_code == 404:
        return EventLocationFailureCategory.NOT_FOUND
    if status_code == 429:
        return EventLocationFailureCategory.RATE_LIMITED
    if status_code in {401, 403}:
        return EventLocationFailureCategory.QUOTA_EXCEEDED
    if status_code == 408 or 500 <= status_code <= 599:
        return EventLocationFailureCategory.TRANSIENT
    return EventLocationFailureCategory.UNAVAILABLE


def _route_status_category(status_code: int) -> RouteFailureCategory:
    if status_code == 400:
        return RouteFailureCategory.INVALID_INPUT
    if status_code == 429:
        return RouteFailureCategory.RATE_LIMITED
    if status_code in {401, 403}:
        return RouteFailureCategory.QUOTA_EXCEEDED
    if status_code == 408 or 500 <= status_code <= 599:
        return RouteFailureCategory.TRANSIENT
    return RouteFailureCategory.UNAVAILABLE


def _sender_category(
    failure: InjectedHttpFailure, *, geocode: bool
) -> EventLocationFailureCategory | RouteFailureCategory:
    if failure.category is InjectedHttpFailureCategory.TRANSIENT:
        return (
            EventLocationFailureCategory.TRANSIENT
            if geocode
            else RouteFailureCategory.TRANSIENT
        )
    return (
        EventLocationFailureCategory.UNAVAILABLE
        if geocode
        else RouteFailureCategory.UNAVAILABLE
    )


class _GeoapifyHttpSender(Protocol):
    """Injected I/O boundary shared by production and synthetic tests."""

    async def send(self, request: InjectedHttpRequest) -> InjectedHttpResult: ...


class GeoapifyHttpGeocodeTransport:
    """Geoapify forward-geocoding transport over an injected sender."""

    def __init__(
        self,
        *,
        sender: _GeoapifyHttpSender,
        now: Callable[[], datetime],
    ) -> None:
        self._sender = sender
        self._now = now

    async def geocode(
        self, query: GeoapifyGeocodeQuery
    ) -> GeoapifyGeocodeTransportResult:
        result = await self._sender.send(_geocode_request(query))
        occurred_at = _require_aware(self._now())
        if isinstance(result, InjectedHttpFailure):
            return GeoapifyGeocodeFailure(
                cast(
                    EventLocationFailureCategory,
                    _sender_category(result, geocode=True),
                ),
                occurred_at,
            )
        if result.status_code != 200:
            return GeoapifyGeocodeFailure(
                _geocode_status_category(result.status_code), occurred_at
            )
        try:
            coordinates = _decode_geocode(result.json_body)
        except _MalformedResponseError:
            return GeoapifyGeocodeFailure(
                EventLocationFailureCategory.UNAVAILABLE, occurred_at
            )
        if coordinates is None:
            return GeoapifyGeocodeFailure(
                EventLocationFailureCategory.NOT_FOUND, occurred_at
            )
        return GeoapifyGeocodeResponse(coordinates)


class GeoapifyHttpRouteTransport:
    """Geoapify road-routing transport over an injected sender."""

    def __init__(
        self,
        *,
        sender: _GeoapifyHttpSender,
        api_key: str,
        now: Callable[[], datetime],
    ) -> None:
        self._sender = sender
        self._api_key = _require_key(api_key)
        self._now = now

    async def route(self, query: GeoapifyRouteQuery) -> GeoapifyRouteTransportResult:
        result = await self._sender.send(_route_request(query, self._api_key))
        occurred_at = _require_aware(self._now())
        if isinstance(result, InjectedHttpFailure):
            return GeoapifyRouteFailure(
                cast(
                    RouteFailureCategory,
                    _sender_category(result, geocode=False),
                ),
                occurred_at,
            )
        if result.status_code != 200:
            return GeoapifyRouteFailure(
                _route_status_category(result.status_code), occurred_at
            )
        try:
            distance_m, duration_s = _decode_route(result.json_body)
        except _MalformedResponseError:
            return GeoapifyRouteFailure(RouteFailureCategory.UNAVAILABLE, occurred_at)
        return GeoapifyRouteResponse(distance_m, duration_s, occurred_at)
