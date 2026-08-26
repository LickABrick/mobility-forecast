"""Profile-scoped, versioned serialization for durable forecast state.

This module is dependency-free so its schema and migration boundary can be tested
without a Home Assistant installation. Stored values may contain operationally
private identifiers and coordinates; callers must use the config-entry-scoped key
and must never expose raw payloads through diagnostics or logs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import cast

from .domain.actuals_forecasting import ActualDistance, PendingDay
from .domain.models import (
    Coordinates,
    DataQuality,
    LocationProvenance,
    ResolvedLocation,
    Route,
)
from .domain.planning import PlannedLeg, PlannedStop, PlanRevision

STORAGE_SCHEMA_VERSION = 1
_STORAGE_KEY_PREFIX = "mobility_forecast"


@dataclass(frozen=True, slots=True)
class ProfileState:
    """Immutable state owned by exactly one Home Assistant config entry."""

    revisions: tuple[PlanRevision, ...]
    pending_days: tuple[PendingDay, ...]
    actuals: tuple[ActualDistance, ...]

    def __post_init__(self) -> None:
        revision_ids = tuple(item.revision_id for item in self.revisions)
        if len(set(revision_ids)) != len(revision_ids):
            raise ValueError("revision identifiers must be unique")
        if any(
            later.created_at <= earlier.created_at
            for earlier, later in zip(self.revisions, self.revisions[1:], strict=False)
        ):
            raise ValueError("revisions must be ordered by increasing creation time")

        pending_dates = tuple(item.service_date for item in self.pending_days)
        if len(set(pending_dates)) != len(pending_dates):
            raise ValueError("pending service dates must be unique")

        actual_ids = tuple(item.revision_id for item in self.actuals)
        if len(set(actual_ids)) != len(actual_ids):
            raise ValueError("actual revision identifiers must be unique")


def profile_storage_key(config_entry_id: str) -> str:
    """Return the private storage namespace for one config entry, never its title."""

    if not config_entry_id.strip():
        raise ValueError("config_entry_id must not be empty")
    return f"{_STORAGE_KEY_PREFIX}.{config_entry_id}"


def _location_to_dict(value: ResolvedLocation | None) -> object:
    if value is None:
        return None
    return {
        "endpoint_id": value.endpoint_id,
        "coordinates": {
            "latitude": value.coordinates.latitude,
            "longitude": value.coordinates.longitude,
        },
        "provenance": value.provenance.value,
        "observed_at": value.observed_at.isoformat() if value.observed_at else None,
        "quality": value.quality.value,
    }


def _route_to_dict(value: Route | None) -> object:
    if value is None:
        return None
    return {
        "origin": _location_to_dict(value.origin),
        "destination": _location_to_dict(value.destination),
        "distance_m": value.distance_m,
        "duration_s": value.duration_s,
        "provider": value.provider,
        "observed_at": value.observed_at.isoformat(),
        "quality": value.quality.value,
    }


def _revision_to_dict(value: PlanRevision) -> dict[str, object]:
    return {
        "revision_id": value.revision_id,
        "service_date": value.service_date.isoformat(),
        "created_at": value.created_at.isoformat(),
        "source_observed_at": value.source_observed_at.isoformat(),
        "stops": [
            {
                "event_id": stop.event_id,
                "starts_at": stop.starts_at.isoformat(),
                "ends_at": stop.ends_at.isoformat(),
                "destination": _location_to_dict(stop.destination),
                "destination_reason": stop.destination_reason,
                "source_references": [
                    list(reference) for reference in stop.source_references
                ],
            }
            for stop in value.stops
        ],
        "legs": [
            {
                "stop_index": leg.stop_index,
                "origin": _location_to_dict(leg.origin),
                "destination": _location_to_dict(leg.destination),
                "route": _route_to_dict(leg.route),
                "quality": leg.quality.value,
                "reason_codes": list(leg.reason_codes),
            }
            for leg in value.legs
        ],
        "quality": value.quality.value,
        "reason_codes": list(value.reason_codes),
    }


def encode_profile_state(state: ProfileState) -> dict[str, object]:
    """Encode immutable state as a JSON-safe schema-version-1 mapping."""

    return {
        "version": STORAGE_SCHEMA_VERSION,
        "revisions": [_revision_to_dict(item) for item in state.revisions],
        "pending_days": [
            {
                "service_date": item.service_date.isoformat(),
                "revision_id": item.revision_id,
                "planned_distance_m": item.planned_distance_m,
                "opened_at": item.opened_at.isoformat(),
                "start_observed_at": item.start_observed_at.isoformat(),
                "start_odometer_km": item.start_odometer_km,
            }
            for item in state.pending_days
        ],
        "actuals": [
            {
                "service_date": item.service_date.isoformat(),
                "revision_id": item.revision_id,
                "planned_distance_m": item.planned_distance_m,
                "actual_distance_m": item.actual_distance_m,
                "closed_at": item.closed_at.isoformat(),
                "quality": item.quality.value,
            }
            for item in state.actuals
        ],
    }


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    result = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in result):
        raise ValueError(f"{field_name} must have string keys")
    return cast(Mapping[str, object], result)


def _sequence(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    return cast(list[object], value)


def _required(mapping: Mapping[str, object], key: str) -> object:
    if key not in mapping:
        raise ValueError(f"missing required storage field: {key}")
    return mapping[key]


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
    text = _string(value, field_name)
    try:
        result = datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO datetime") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return result


def _optional_datetime(value: object, field_name: str) -> datetime | None:
    return None if value is None else _datetime(value, field_name)


def _date(value: object, field_name: str) -> date:
    text = _string(value, field_name)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO date") from error


def _quality(value: object, field_name: str) -> DataQuality:
    try:
        return DataQuality(_string(value, field_name))
    except ValueError as error:
        raise ValueError(f"{field_name} has an unknown quality") from error


def _strings(value: object, field_name: str) -> tuple[str, ...]:
    return tuple(
        _string(item, field_name) for item in _sequence(value, field_name)
    )


def _location_from_dict(value: object, field_name: str) -> ResolvedLocation | None:
    if value is None:
        return None
    item = _mapping(value, field_name)
    coordinates = _mapping(_required(item, "coordinates"), f"{field_name}.coordinates")
    try:
        provenance = LocationProvenance(
            _string(_required(item, "provenance"), f"{field_name}.provenance")
        )
    except ValueError as error:
        raise ValueError(f"{field_name}.provenance is unknown") from error
    return ResolvedLocation(
        endpoint_id=_string(
            _required(item, "endpoint_id"), f"{field_name}.endpoint_id"
        ),
        coordinates=Coordinates(
            latitude=_number(
                _required(coordinates, "latitude"), f"{field_name}.coordinates.latitude"
            ),
            longitude=_number(
                _required(coordinates, "longitude"),
                f"{field_name}.coordinates.longitude",
            ),
        ),
        provenance=provenance,
        observed_at=_optional_datetime(
            _required(item, "observed_at"), f"{field_name}.observed_at"
        ),
        quality=_quality(_required(item, "quality"), f"{field_name}.quality"),
    )


def _route_from_dict(value: object, field_name: str) -> Route | None:
    if value is None:
        return None
    item = _mapping(value, field_name)
    origin = _location_from_dict(_required(item, "origin"), f"{field_name}.origin")
    destination = _location_from_dict(
        _required(item, "destination"), f"{field_name}.destination"
    )
    if origin is None or destination is None:
        raise ValueError(f"{field_name} endpoints must not be null")
    return Route(
        origin=origin,
        destination=destination,
        distance_m=_integer(_required(item, "distance_m"), f"{field_name}.distance_m"),
        duration_s=_integer(_required(item, "duration_s"), f"{field_name}.duration_s"),
        provider=_string(_required(item, "provider"), f"{field_name}.provider"),
        observed_at=_datetime(
            _required(item, "observed_at"), f"{field_name}.observed_at"
        ),
        quality=_quality(_required(item, "quality"), f"{field_name}.quality"),
    )


def _stop_from_dict(value: object, index: int) -> PlannedStop:
    field_name = f"revisions.stops[{index}]"
    item = _mapping(value, field_name)
    references: list[tuple[str, str]] = []
    for value in _sequence(
        _required(item, "source_references"), f"{field_name}.source_references"
    ):
        pair = _sequence(value, f"{field_name}.source_references")
        if len(pair) != 2:
            raise ValueError(f"{field_name}.source_references must contain pairs")
        references.append(
            (
                _string(pair[0], f"{field_name}.source_references"),
                _string(pair[1], f"{field_name}.source_references"),
            )
        )
    return PlannedStop(
        event_id=_string(_required(item, "event_id"), f"{field_name}.event_id"),
        starts_at=_datetime(_required(item, "starts_at"), f"{field_name}.starts_at"),
        ends_at=_datetime(_required(item, "ends_at"), f"{field_name}.ends_at"),
        destination=_location_from_dict(
            _required(item, "destination"), f"{field_name}.destination"
        ),
        destination_reason=_string(
            _required(item, "destination_reason"), f"{field_name}.destination_reason"
        ),
        source_references=tuple(references),
    )


def _leg_from_dict(value: object, index: int) -> PlannedLeg:
    field_name = f"revisions.legs[{index}]"
    item = _mapping(value, field_name)
    return PlannedLeg(
        stop_index=_integer(
            _required(item, "stop_index"), f"{field_name}.stop_index"
        ),
        origin=_location_from_dict(_required(item, "origin"), f"{field_name}.origin"),
        destination=_location_from_dict(
            _required(item, "destination"), f"{field_name}.destination"
        ),
        route=_route_from_dict(_required(item, "route"), f"{field_name}.route"),
        quality=_quality(_required(item, "quality"), f"{field_name}.quality"),
        reason_codes=_strings(
            _required(item, "reason_codes"), f"{field_name}.reason_codes"
        ),
    )


def _revision_from_dict(value: object) -> PlanRevision:
    item = _mapping(value, "revision")
    stops = tuple(
        _stop_from_dict(stop, index)
        for index, stop in enumerate(
            _sequence(_required(item, "stops"), "revision.stops")
        )
    )
    legs = tuple(
        _leg_from_dict(leg, index)
        for index, leg in enumerate(
            _sequence(_required(item, "legs"), "revision.legs")
        )
    )
    return PlanRevision(
        revision_id=_string(_required(item, "revision_id"), "revision.revision_id"),
        service_date=_date(
            _required(item, "service_date"), "revision.service_date"
        ),
        created_at=_datetime(_required(item, "created_at"), "revision.created_at"),
        source_observed_at=_datetime(
            _required(item, "source_observed_at"), "revision.source_observed_at"
        ),
        stops=stops,
        legs=legs,
        quality=_quality(_required(item, "quality"), "revision.quality"),
        reason_codes=_strings(
            _required(item, "reason_codes"), "revision.reason_codes"
        ),
    )


def _pending_from_dict(value: object) -> PendingDay:
    item = _mapping(value, "pending_day")
    return PendingDay(
        service_date=_date(_required(item, "service_date"), "pending_day.service_date"),
        revision_id=_string(_required(item, "revision_id"), "pending_day.revision_id"),
        planned_distance_m=_integer(
            _required(item, "planned_distance_m"), "pending_day.planned_distance_m"
        ),
        opened_at=_datetime(_required(item, "opened_at"), "pending_day.opened_at"),
        start_observed_at=_datetime(
            _required(item, "start_observed_at"), "pending_day.start_observed_at"
        ),
        start_odometer_km=_number(
            _required(item, "start_odometer_km"), "pending_day.start_odometer_km"
        ),
    )


def _actual_from_dict(value: object) -> ActualDistance:
    item = _mapping(value, "actual")
    return ActualDistance(
        service_date=_date(_required(item, "service_date"), "actual.service_date"),
        revision_id=_string(_required(item, "revision_id"), "actual.revision_id"),
        planned_distance_m=_integer(
            _required(item, "planned_distance_m"), "actual.planned_distance_m"
        ),
        actual_distance_m=_integer(
            _required(item, "actual_distance_m"), "actual.actual_distance_m"
        ),
        closed_at=_datetime(_required(item, "closed_at"), "actual.closed_at"),
        quality=_quality(_required(item, "quality"), "actual.quality"),
    )


def decode_profile_state(payload: object) -> ProfileState:
    """Decode schema version 1, failing closed before any future migration.

    Future schema versions must add an explicit migration step before this
    function accepts them; silently interpreting another version is forbidden.
    """

    root = _mapping(payload, "storage payload")
    version = _integer(_required(root, "version"), "version")
    if version != STORAGE_SCHEMA_VERSION:
        raise ValueError(f"unsupported storage schema version: {version}")
    return ProfileState(
        revisions=tuple(
            _revision_from_dict(item)
            for item in _sequence(_required(root, "revisions"), "revisions")
        ),
        pending_days=tuple(
            _pending_from_dict(item)
            for item in _sequence(_required(root, "pending_days"), "pending_days")
        ),
        actuals=tuple(
            _actual_from_dict(item)
            for item in _sequence(_required(root, "actuals"), "actuals")
        ),
    )
