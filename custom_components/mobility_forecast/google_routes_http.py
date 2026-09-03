"""Synthetic-testable Google Geocoding and Routes HTTP shaping.

The concrete transports in this module stop at the shared injected HTTP sender.
They do not open sockets, resolve DNS, or log requests. Request URLs,
credentials, location text, coordinates, and response bodies are excluded from
representations.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, cast

from .domain.event_locations import EventLocationFailureCategory
from .domain.models import Coordinates
from .domain.routing import RouteFailureCategory
from .google_routes import (
    GoogleGeocodeFailure,
    GoogleGeocodeQuery,
    GoogleGeocodeResponse,
    GoogleGeocodeTransportResult,
    GoogleRoutesFailure,
    GoogleRoutesQuery,
    GoogleRoutesResponse,
    GoogleRoutesTransportResult,
)
from .openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResult,
)
from .route_provider_config import (
    GOOGLE_GEOCODING_ENDPOINT,
    GOOGLE_ROUTING_ENDPOINT,
)

ROUTING_FIELD_MASK = "routes.distanceMeters,routes.duration"


class _MalformedResponseError(ValueError):
    """Internal marker for an invalid provider success payload."""


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("current time must be timezone-aware")
    return value


def _geocode_headers() -> tuple[tuple[str, str], ...]:
    return (("Accept", "application/json"),)


def _route_headers(api_key: str) -> tuple[tuple[str, str], ...]:
    return (
        ("Accept", "application/json"),
        ("Content-Type", "application/json"),
        ("X-Goog-Api-Key", api_key),
        ("X-Goog-FieldMask", ROUTING_FIELD_MASK),
    )


def _require_key(api_key: str) -> str:
    if not api_key.strip():
        raise ValueError("API key must not be empty")
    return api_key


def _geocode_request(query: GoogleGeocodeQuery) -> InjectedHttpRequest:
    return InjectedHttpRequest(
        method="GET",
        url=GOOGLE_GEOCODING_ENDPOINT,
        headers=_geocode_headers(),
        query=(("address", query.location_text), ("key", query.api_key)),
        json_body=None,
    )


def _departure_time(depart_at: datetime) -> str:
    return (
        depart_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _route_body(query: GoogleRoutesQuery) -> dict[str, object]:
    body: dict[str, object] = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": query.origin.latitude,
                    "longitude": query.origin.longitude,
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": query.destination.latitude,
                    "longitude": query.destination.longitude,
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    modifiers: dict[str, bool] = {}
    if query.avoid_tolls:
        modifiers["avoidTolls"] = True
    if query.avoid_highways:
        modifiers["avoidHighways"] = True
    if modifiers:
        body["routeModifiers"] = modifiers
    if query.depart_at is not None:
        body["departureTime"] = _departure_time(query.depart_at)
    return body


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
    if isinstance(value, bool):
        raise _MalformedResponseError
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError as error:
            raise _MalformedResponseError from error
    else:
        raise _MalformedResponseError
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
    results = _sequence(_mapping(body).get("results"))
    if not results:
        return None
    geometry = _mapping(_mapping(results[0]).get("geometry"))
    location = _mapping(geometry.get("location"))
    return _coordinate(location.get("lng"), location.get("lat"))


def _geocode_provider_status_category(
    body: object,
) -> EventLocationFailureCategory | None:
    status = _mapping(body).get("status")
    if status == "OK":
        return None
    categories = {
        "ZERO_RESULTS": EventLocationFailureCategory.NOT_FOUND,
        "OVER_DAILY_LIMIT": EventLocationFailureCategory.QUOTA_EXCEEDED,
        "OVER_QUERY_LIMIT": EventLocationFailureCategory.QUOTA_EXCEEDED,
        "REQUEST_DENIED": EventLocationFailureCategory.QUOTA_EXCEEDED,
        "INVALID_REQUEST": EventLocationFailureCategory.INVALID_INPUT,
        "UNKNOWN_ERROR": EventLocationFailureCategory.TRANSIENT,
    }
    if not isinstance(status, str):
        return EventLocationFailureCategory.UNAVAILABLE
    return categories.get(status, EventLocationFailureCategory.UNAVAILABLE)


def _decode_route(body: object) -> tuple[int, int]:
    routes = _sequence(_mapping(body).get("routes"))
    if not routes:
        raise _MalformedResponseError
    first_route = _mapping(routes[0])
    duration = first_route.get("duration")
    if not isinstance(duration, str) or not duration.endswith("s"):
        raise _MalformedResponseError
    return (
        _positive_ceiling(first_route.get("distanceMeters")),
        _positive_ceiling(duration.removesuffix("s")),
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
    result: InjectedHttpFailure,
    *,
    geocode: bool,
) -> EventLocationFailureCategory | RouteFailureCategory:
    if result.category is InjectedHttpFailureCategory.TRANSIENT:
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


class _GoogleHttpSender(Protocol):
    """Injected I/O boundary; production and tests share this protocol."""

    async def send(self, request: InjectedHttpRequest) -> InjectedHttpResult: ...


class GoogleHttpGeocodeTransport:
    """Google Geocoding transport over one injected HTTP sender."""

    def __init__(
        self,
        *,
        sender: _GoogleHttpSender,
        now: Callable[[], datetime],
    ) -> None:
        self._sender = sender
        self._now = now

    async def geocode(self, query: GoogleGeocodeQuery) -> GoogleGeocodeTransportResult:
        result = await self._sender.send(_geocode_request(query))
        occurred_at = _require_aware(self._now())
        if isinstance(result, InjectedHttpFailure):
            return GoogleGeocodeFailure(
                cast(
                    EventLocationFailureCategory,
                    _sender_category(result, geocode=True),
                ),
                occurred_at,
            )
        response = result
        if response.status_code != 200:
            return GoogleGeocodeFailure(
                _geocode_status_category(response.status_code), occurred_at
            )
        try:
            failure_category = _geocode_provider_status_category(response.json_body)
            if failure_category is not None:
                return GoogleGeocodeFailure(failure_category, occurred_at)
            coordinates = _decode_geocode(response.json_body)
        except _MalformedResponseError:
            return GoogleGeocodeFailure(
                EventLocationFailureCategory.UNAVAILABLE, occurred_at
            )
        if coordinates is None:
            return GoogleGeocodeFailure(
                EventLocationFailureCategory.NOT_FOUND, occurred_at
            )
        return GoogleGeocodeResponse(coordinates)


class GoogleHttpRouteTransport:
    """Google Routes transport over one injected HTTP sender.

    The route query is provider-neutral and carries no credential; the selected
    profile key is bound once at construction and never re-exposed.
    """

    def __init__(
        self,
        *,
        sender: _GoogleHttpSender,
        api_key: str,
        now: Callable[[], datetime],
    ) -> None:
        self._sender = sender
        self._api_key = _require_key(api_key)
        self._now = now

    async def compute_route(
        self, query: GoogleRoutesQuery
    ) -> GoogleRoutesTransportResult:
        request = InjectedHttpRequest(
            method="POST",
            url=GOOGLE_ROUTING_ENDPOINT,
            headers=_route_headers(self._api_key),
            query=(),
            json_body=_route_body(query),
        )
        result = await self._sender.send(request)
        occurred_at = _require_aware(self._now())
        if isinstance(result, InjectedHttpFailure):
            return GoogleRoutesFailure(
                cast(
                    RouteFailureCategory,
                    _sender_category(result, geocode=False),
                ),
                occurred_at,
            )
        response = result
        if response.status_code != 200:
            return GoogleRoutesFailure(
                _route_status_category(response.status_code), occurred_at
            )
        try:
            distance_m, duration_s = _decode_route(response.json_body)
        except _MalformedResponseError:
            return GoogleRoutesFailure(RouteFailureCategory.UNAVAILABLE, occurred_at)
        return GoogleRoutesResponse(distance_m, duration_s, occurred_at)
