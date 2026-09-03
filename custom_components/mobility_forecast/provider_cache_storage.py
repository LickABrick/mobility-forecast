"""Versioned profile-scoped persistence for private provider caches."""

from __future__ import annotations

import base64
import binascii
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import cast

from .domain.models import (
    Coordinates,
    DataQuality,
    LocationProvenance,
    ResolvedLocation,
    Route,
)
from .domain.routing import RouteCacheEntry, RouteCacheKey
from .openrouteservice import GeocodeCacheEntry
from .provider_guardrails import GeocodeCacheKey

PROVIDER_CACHE_STORAGE_SCHEMA_VERSION = 1
PRIVACY_KEY_BYTES = 32
_STORAGE_KEY_PREFIX = "mobility_forecast.provider_cache"


@dataclass(frozen=True, slots=True)
class ProviderCacheState:
    """Private immutable cache state owned by one config entry."""

    privacy_key: bytes = field(repr=False)
    geocodes: tuple[tuple[GeocodeCacheKey, GeocodeCacheEntry], ...] = field(repr=False)
    routes: tuple[tuple[RouteCacheKey, RouteCacheEntry], ...] = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.privacy_key) != PRIVACY_KEY_BYTES:
            raise ValueError("privacy key must contain exactly 32 bytes")
        geocode_keys = tuple(key for key, _entry in self.geocodes)
        if len(set(geocode_keys)) != len(geocode_keys):
            raise ValueError("geocode cache keys must be unique")
        route_keys = tuple(key for key, _entry in self.routes)
        if len(set(route_keys)) != len(route_keys):
            raise ValueError("route cache keys must be unique")


def provider_cache_storage_key(config_entry_id: str) -> str:
    """Return a private provider-cache namespace for one config entry."""

    if not config_entry_id.strip():
        raise ValueError("config_entry_id must not be empty")
    return f"{_STORAGE_KEY_PREFIX}.{config_entry_id}"


def _location_to_dict(value: ResolvedLocation) -> dict[str, object]:
    return {
        "endpoint_id": value.endpoint_id,
        "latitude": value.coordinates.latitude,
        "longitude": value.coordinates.longitude,
        "provenance": value.provenance.value,
        "observed_at": value.observed_at.isoformat() if value.observed_at else None,
        "quality": value.quality.value,
    }


def _route_to_dict(value: Route) -> dict[str, object]:
    return {
        "origin": _location_to_dict(value.origin),
        "destination": _location_to_dict(value.destination),
        "distance_m": value.distance_m,
        "duration_s": value.duration_s,
        "provider": value.provider,
        "observed_at": value.observed_at.isoformat(),
        "quality": value.quality.value,
    }


def encode_provider_cache_state(state: ProviderCacheState) -> dict[str, object]:
    """Encode private state into its strict JSON-safe schema."""

    return {
        "version": PROVIDER_CACHE_STORAGE_SCHEMA_VERSION,
        "privacy_key": base64.b64encode(state.privacy_key).decode("ascii"),
        "geocodes": [
            {
                "key": key.digest,
                "latitude": entry.coordinates.latitude,
                "longitude": entry.coordinates.longitude,
                "stored_at": entry.stored_at.isoformat(),
            }
            for key, entry in state.geocodes
        ],
        "routes": [
            {
                "key": key.digest,
                "route": _route_to_dict(entry.route),
                "stored_at": entry.stored_at.isoformat(),
            }
            for key, entry in state.routes
        ],
    }


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    result = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in result):
        raise ValueError(f"{field_name} must have string keys")
    return cast(Mapping[str, object], result)


def _required(value: Mapping[str, object], key: str) -> object:
    if key not in value:
        raise ValueError(f"missing required provider cache field: {key}")
    return value[key]


def _array(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    return cast(list[object], value)


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _datetime(value: object, field_name: str) -> datetime:
    try:
        result = datetime.fromisoformat(_string(value, field_name))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO datetime") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return result


def _location_from_dict(value: object, field_name: str) -> ResolvedLocation:
    item = _mapping(value, field_name)
    observed_value = _required(item, "observed_at")
    try:
        provenance = LocationProvenance(
            _string(_required(item, "provenance"), f"{field_name}.provenance")
        )
        quality = DataQuality(
            _string(_required(item, "quality"), f"{field_name}.quality")
        )
    except ValueError as error:
        raise ValueError(f"{field_name} has an unknown enum value") from error
    return ResolvedLocation(
        endpoint_id=_string(
            _required(item, "endpoint_id"), f"{field_name}.endpoint_id"
        ),
        coordinates=Coordinates(
            _number(_required(item, "latitude"), f"{field_name}.latitude"),
            _number(_required(item, "longitude"), f"{field_name}.longitude"),
        ),
        provenance=provenance,
        observed_at=(
            None
            if observed_value is None
            else _datetime(observed_value, f"{field_name}.observed_at")
        ),
        quality=quality,
    )


def _route_from_dict(value: object, field_name: str) -> Route:
    item = _mapping(value, field_name)
    try:
        quality = DataQuality(
            _string(_required(item, "quality"), f"{field_name}.quality")
        )
    except ValueError as error:
        raise ValueError(f"{field_name}.quality is unknown") from error
    return Route(
        origin=_location_from_dict(_required(item, "origin"), f"{field_name}.origin"),
        destination=_location_from_dict(
            _required(item, "destination"), f"{field_name}.destination"
        ),
        distance_m=_integer(_required(item, "distance_m"), f"{field_name}.distance_m"),
        duration_s=_integer(_required(item, "duration_s"), f"{field_name}.duration_s"),
        provider=_string(_required(item, "provider"), f"{field_name}.provider"),
        observed_at=_datetime(
            _required(item, "observed_at"), f"{field_name}.observed_at"
        ),
        quality=quality,
    )


def decode_provider_cache_state(payload: object) -> ProviderCacheState:
    """Decode strict state and fail closed for unsupported or malformed data."""

    root = _mapping(payload, "provider cache payload")
    version = _required(root, "version")
    if version != PROVIDER_CACHE_STORAGE_SCHEMA_VERSION:
        raise ValueError("unsupported provider cache schema version")
    encoded_key = _string(_required(root, "privacy_key"), "privacy_key")
    try:
        privacy_key = base64.b64decode(encoded_key, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("privacy key must be valid base64") from error

    geocodes: list[tuple[GeocodeCacheKey, GeocodeCacheEntry]] = []
    for index, raw_item in enumerate(_array(_required(root, "geocodes"), "geocodes")):
        field_name = f"geocodes[{index}]"
        item = _mapping(raw_item, field_name)
        geocodes.append(
            (
                GeocodeCacheKey(_string(_required(item, "key"), f"{field_name}.key")),
                GeocodeCacheEntry(
                    Coordinates(
                        _number(_required(item, "latitude"), f"{field_name}.latitude"),
                        _number(
                            _required(item, "longitude"), f"{field_name}.longitude"
                        ),
                    ),
                    _datetime(_required(item, "stored_at"), f"{field_name}.stored_at"),
                ),
            )
        )

    routes: list[tuple[RouteCacheKey, RouteCacheEntry]] = []
    for index, raw_item in enumerate(_array(_required(root, "routes"), "routes")):
        field_name = f"routes[{index}]"
        item = _mapping(raw_item, field_name)
        routes.append(
            (
                RouteCacheKey(_string(_required(item, "key"), f"{field_name}.key")),
                RouteCacheEntry(
                    _route_from_dict(_required(item, "route"), f"{field_name}.route"),
                    _datetime(_required(item, "stored_at"), f"{field_name}.stored_at"),
                ),
            )
        )
    return ProviderCacheState(privacy_key, tuple(geocodes), tuple(routes))


def prune_provider_cache_state(
    state: ProviderCacheState,
    *,
    evaluated_at: datetime,
    maximum_geocode_age: timedelta,
    maximum_route_age: timedelta,
) -> ProviderCacheState:
    """Return state without expired or future-dated cache entries."""

    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    if maximum_geocode_age <= timedelta(0) or maximum_route_age <= timedelta(0):
        raise ValueError("cache retention ages must be positive")

    def retained(stored_at: datetime, maximum_age: timedelta) -> bool:
        age = evaluated_at - stored_at
        return timedelta(0) <= age <= maximum_age

    return ProviderCacheState(
        state.privacy_key,
        tuple(
            item
            for item in state.geocodes
            if retained(item[1].stored_at, maximum_geocode_age)
        ),
        tuple(
            item
            for item in state.routes
            if retained(item[1].stored_at, maximum_route_age)
        ),
    )
