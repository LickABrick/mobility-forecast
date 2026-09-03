"""Synthetic-testable OpenRouteService HTTP shaping and response decoding.

The concrete transports in this module stop at an injected HTTP sender. They do
not open sockets, resolve DNS, log requests, or compose into the Home Assistant
runtime. Request URLs, credentials, location text, coordinates, and response
bodies are excluded from representations.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, cast

from .domain.event_locations import EventLocationFailureCategory
from .domain.models import Coordinates
from .domain.routing import RouteFailureCategory
from .openrouteservice import (
    ORS_HOSTED_GEOCODING_ENDPOINT,
    ORS_HOSTED_ROUTING_ENDPOINT,
    OpenRouteServiceGeocodeFailure,
    OpenRouteServiceGeocodeQuery,
    OpenRouteServiceGeocodeResponse,
    OpenRouteServiceGeocodeTransportResult,
    OpenRouteServiceRouteFailure,
    OpenRouteServiceRouteQuery,
    OpenRouteServiceRouteResponse,
    OpenRouteServiceRouteTransportResult,
)
from .route_provider_config import GeocoderKind


@dataclass(frozen=True, slots=True)
class InjectedHttpRequest:
    """Minimal private HTTP request passed only to an injected sender."""

    method: str
    url: str = field(repr=False)
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    query: tuple[tuple[str, str], ...] = field(repr=False)
    json_body: object = field(repr=False)

    def __post_init__(self) -> None:
        if self.method not in {"GET", "POST"}:
            raise ValueError("HTTP method is unavailable")
        if not self.url.strip():
            raise ValueError("HTTP URL is unavailable")


@dataclass(frozen=True, slots=True)
class InjectedHttpResponse:
    """HTTP status and decoded JSON supplied by a synthetic sender."""

    status_code: int
    json_body: object = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.status_code) is not int or not 100 <= self.status_code <= 599:
            raise ValueError("HTTP status code is unavailable")


class InjectedHttpFailureCategory(StrEnum):
    """Sanitized sender failures independent from provider response details."""

    TRANSIENT = "transient"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class InjectedHttpFailure:
    """Typed sender failure without exception or request text."""

    category: InjectedHttpFailureCategory


type InjectedHttpResult = InjectedHttpResponse | InjectedHttpFailure


class InjectedHttpSender(Protocol):
    """Injected I/O boundary; production HTTP implementation is intentionally absent."""

    async def send(self, request: InjectedHttpRequest) -> InjectedHttpResult:
        """Send one shaped request or return one sanitized sender failure."""
        ...


class _MalformedResponseError(ValueError):
    """Internal marker for an invalid provider success payload."""


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("current time must be timezone-aware")
    return value


def _append_path(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _headers(*, api_key: str | None, json_request: bool) -> tuple[tuple[str, str], ...]:
    headers: list[tuple[str, str]] = [("Accept", "application/json")]
    if json_request:
        headers.append(("Content-Type", "application/json"))
    if api_key is not None:
        headers.append(("Authorization", api_key))
    return tuple(headers)


def _geocode_request(query: OpenRouteServiceGeocodeQuery) -> InjectedHttpRequest:
    if query.api_key is not None:
        if (
            query.endpoint != ORS_HOSTED_GEOCODING_ENDPOINT
            or query.geocoder is not GeocoderKind.PELIAS
        ):
            raise ValueError("hosted geocoding endpoint is unavailable")
        url = query.endpoint
    else:
        if query.endpoint == ORS_HOSTED_GEOCODING_ENDPOINT:
            raise ValueError("hosted geocoding credential is unavailable")
        suffixes = {
            GeocoderKind.PELIAS: "v1/search",
            GeocoderKind.PHOTON: "api",
            GeocoderKind.NOMINATIM: "search",
        }
        url = _append_path(query.endpoint, suffixes[query.geocoder])

    if query.geocoder is GeocoderKind.PELIAS:
        parameters = (("text", query.location_text), ("size", "1"))
    elif query.geocoder is GeocoderKind.PHOTON:
        parameters = (("q", query.location_text), ("limit", "1"))
    else:
        parameters = (
            ("q", query.location_text),
            ("format", "jsonv2"),
            ("limit", "1"),
        )
    return InjectedHttpRequest(
        method="GET",
        url=url,
        headers=_headers(api_key=query.api_key, json_request=False),
        query=parameters,
        json_body=None,
    )


def _route_request(query: OpenRouteServiceRouteQuery) -> InjectedHttpRequest:
    if query.api_key is not None:
        if query.endpoint != ORS_HOSTED_ROUTING_ENDPOINT:
            raise ValueError("hosted routing endpoint is unavailable")
        url = query.endpoint
    else:
        if query.endpoint == ORS_HOSTED_ROUTING_ENDPOINT:
            raise ValueError("hosted routing credential is unavailable")
        url = _append_path(query.endpoint, "v2/directions/driving-car")

    body: dict[str, object] = {
        "coordinates": [
            [query.origin.longitude, query.origin.latitude],
            [query.destination.longitude, query.destination.latitude],
        ],
        "geometry": False,
        "instructions": False,
        "units": "m",
    }
    if query.depart_at is not None:
        body["departure"] = query.depart_at.replace(tzinfo=None).isoformat(
            timespec="seconds"
        )
    avoid_features: list[str] = []
    if query.avoid_tolls:
        avoid_features.append("tollways")
    if query.avoid_highways:
        avoid_features.append("highways")
    if avoid_features:
        body["options"] = {"avoid_features": avoid_features}
    return InjectedHttpRequest(
        method="POST",
        url=url,
        headers=_headers(api_key=query.api_key, json_request=True),
        query=(),
        json_body=body,
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


def _decode_geojson(body: object) -> Coordinates | None:
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


def _decode_nominatim(body: object) -> Coordinates | None:
    results = _sequence(body)
    if not results:
        return None
    result = _mapping(results[0])
    latitude = result.get("lat")
    longitude = result.get("lon")
    if not isinstance(latitude, str) or not isinstance(longitude, str):
        raise _MalformedResponseError
    try:
        parsed_latitude = float(latitude)
        parsed_longitude = float(longitude)
    except ValueError as error:
        raise _MalformedResponseError from error
    return _coordinate(parsed_longitude, parsed_latitude)


def _positive_ceiling(value: object) -> int:
    number = _finite_number(value)
    if number <= 0:
        raise _MalformedResponseError
    return math.ceil(number)


def _decode_route(body: object) -> tuple[int, int]:
    routes = _sequence(_mapping(body).get("routes"))
    if not routes:
        raise _MalformedResponseError
    summary = _mapping(_mapping(routes[0]).get("summary"))
    return (
        _positive_ceiling(summary.get("distance")),
        _positive_ceiling(summary.get("duration")),
    )


def _geocode_status_category(status_code: int) -> EventLocationFailureCategory:
    if status_code == 429:
        return EventLocationFailureCategory.RATE_LIMITED
    if status_code == 408 or 500 <= status_code <= 599:
        return EventLocationFailureCategory.TRANSIENT
    if status_code in {400, 422}:
        return EventLocationFailureCategory.INVALID_INPUT
    return EventLocationFailureCategory.UNAVAILABLE


def _route_status_category(status_code: int) -> RouteFailureCategory:
    if status_code == 429:
        return RouteFailureCategory.RATE_LIMITED
    if status_code == 408 or 500 <= status_code <= 599:
        return RouteFailureCategory.TRANSIENT
    if status_code in {400, 422}:
        return RouteFailureCategory.INVALID_INPUT
    return RouteFailureCategory.UNAVAILABLE


class OpenRouteServiceHttpGeocodeTransport:
    """Pelias, Photon and Nominatim transport over one injected HTTP sender."""

    def __init__(
        self,
        *,
        sender: InjectedHttpSender,
        now: Callable[[], datetime],
    ) -> None:
        self._sender = sender
        self._now = now

    async def geocode(
        self, query: OpenRouteServiceGeocodeQuery
    ) -> OpenRouteServiceGeocodeTransportResult:
        result = await self._sender.send(_geocode_request(query))
        occurred_at = _require_aware(self._now())
        if isinstance(result, InjectedHttpFailure):
            category = (
                EventLocationFailureCategory.TRANSIENT
                if result.category is InjectedHttpFailureCategory.TRANSIENT
                else EventLocationFailureCategory.UNAVAILABLE
            )
            return OpenRouteServiceGeocodeFailure(category, occurred_at)
        if result.status_code != 200:
            return OpenRouteServiceGeocodeFailure(
                _geocode_status_category(result.status_code), occurred_at
            )
        try:
            coordinates = (
                _decode_nominatim(result.json_body)
                if query.geocoder is GeocoderKind.NOMINATIM
                else _decode_geojson(result.json_body)
            )
        except _MalformedResponseError:
            return OpenRouteServiceGeocodeFailure(
                EventLocationFailureCategory.UNAVAILABLE, occurred_at
            )
        if coordinates is None:
            return OpenRouteServiceGeocodeFailure(
                EventLocationFailureCategory.NOT_FOUND, occurred_at
            )
        return OpenRouteServiceGeocodeResponse(coordinates)


class OpenRouteServiceHttpRouteTransport:
    """OpenRouteService directions transport over one injected HTTP sender."""

    def __init__(
        self,
        *,
        sender: InjectedHttpSender,
        now: Callable[[], datetime],
    ) -> None:
        self._sender = sender
        self._now = now

    async def route(
        self, query: OpenRouteServiceRouteQuery
    ) -> OpenRouteServiceRouteTransportResult:
        result = await self._sender.send(_route_request(query))
        occurred_at = _require_aware(self._now())
        if isinstance(result, InjectedHttpFailure):
            category = (
                RouteFailureCategory.TRANSIENT
                if result.category is InjectedHttpFailureCategory.TRANSIENT
                else RouteFailureCategory.UNAVAILABLE
            )
            return OpenRouteServiceRouteFailure(category, occurred_at)
        if result.status_code != 200:
            return OpenRouteServiceRouteFailure(
                _route_status_category(result.status_code), occurred_at
            )
        try:
            distance_m, duration_s = _decode_route(result.json_body)
        except _MalformedResponseError:
            return OpenRouteServiceRouteFailure(
                RouteFailureCategory.UNAVAILABLE, occurred_at
            )
        return OpenRouteServiceRouteResponse(distance_m, duration_s, occurred_at)
