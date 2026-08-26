"""Pure endpoint resolution with explicit freshness and fallback policy."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from .models import (
    Coordinates,
    DataQuality,
    LocationProvenance,
    ResolvedLocation,
)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class LocationResolutionReason(StrEnum):
    """Privacy-safe reason for the selected endpoint resolution path."""

    VEHICLE_ACCEPTED = "vehicle_accepted"
    PRIMARY_ACCEPTED = "primary_accepted"
    VEHICLE_MISSING = "vehicle_missing"
    VEHICLE_OBSERVATION_TIME_MISSING = "vehicle_observation_time_missing"
    VEHICLE_OBSERVED_IN_FUTURE = "vehicle_observed_in_future"
    VEHICLE_STALE = "vehicle_stale"
    VEHICLE_ACCURACY_UNKNOWN = "vehicle_accuracy_unknown"
    VEHICLE_INACCURATE = "vehicle_inaccurate"
    TRIP_BEYOND_VEHICLE_HORIZON = "trip_beyond_vehicle_horizon"
    PRIMARY_MISSING = "primary_missing"


@dataclass(frozen=True, slots=True)
class LocationCandidate:
    """Operational endpoint candidate; coordinates stay out of representations."""

    endpoint_id: str
    coordinates: Coordinates = field(repr=False)
    provenance: LocationProvenance
    observed_at: datetime | None
    accuracy_m: float | None

    def __post_init__(self) -> None:
        if not self.endpoint_id.strip():
            raise ValueError("endpoint_id must not be empty")
        if self.observed_at is not None:
            _require_aware(self.observed_at, "observed_at")
        if self.accuracy_m is not None and (
            not math.isfinite(self.accuracy_m) or self.accuracy_m < 0
        ):
            raise ValueError("accuracy_m must be finite and non-negative")

    def as_resolved(self, quality: DataQuality) -> ResolvedLocation:
        """Convert an accepted candidate to the existing endpoint contract."""

        return ResolvedLocation(
            endpoint_id=self.endpoint_id,
            coordinates=self.coordinates,
            provenance=self.provenance,
            observed_at=self.observed_at,
            quality=quality,
        )


@dataclass(frozen=True, slots=True)
class StartLocationPolicy:
    """Required, visible gates for use of a passive vehicle location."""

    maximum_vehicle_age: timedelta
    maximum_vehicle_accuracy_m: float
    maximum_vehicle_trip_horizon: timedelta

    def __post_init__(self) -> None:
        if self.maximum_vehicle_age <= timedelta(0):
            raise ValueError("maximum_vehicle_age must be positive")
        if (
            not math.isfinite(self.maximum_vehicle_accuracy_m)
            or self.maximum_vehicle_accuracy_m <= 0
        ):
            raise ValueError("maximum_vehicle_accuracy_m must be finite and positive")
        if self.maximum_vehicle_trip_horizon <= timedelta(0):
            raise ValueError("maximum_vehicle_trip_horizon must be positive")


@dataclass(frozen=True, slots=True)
class EndLocationPolicy:
    """Explicitly permits or forbids a configured destination fallback."""

    allow_configured_fallback: bool


@dataclass(frozen=True, slots=True)
class LocationResolution:
    """Resolved endpoint or an explicit unavailable result."""

    location: ResolvedLocation | None
    reason: LocationResolutionReason

    @property
    def quality(self) -> DataQuality:
        if self.location is None:
            return DataQuality.UNAVAILABLE
        return self.location.quality


def _fallback_or_unavailable(
    fallback: LocationCandidate | None,
    reason: LocationResolutionReason,
    *,
    allowed: bool = True,
) -> LocationResolution:
    if (
        fallback is not None
        and fallback.provenance is not LocationProvenance.CONFIGURED_FALLBACK
    ):
        raise ValueError("fallback must have configured-fallback provenance")
    if allowed and fallback is not None:
        return LocationResolution(
            location=fallback.as_resolved(DataQuality.PARTIAL),
            reason=reason,
        )
    return LocationResolution(location=None, reason=reason)


def resolve_start_location(
    *,
    trip_starts_at: datetime,
    evaluated_at: datetime,
    policy: StartLocationPolicy,
    vehicle_location: LocationCandidate | None,
    fallback: LocationCandidate | None,
) -> LocationResolution:
    """Resolve an origin without refreshing or otherwise contacting a vehicle."""

    _require_aware(trip_starts_at, "trip_starts_at")
    _require_aware(evaluated_at, "evaluated_at")
    trip_horizon = trip_starts_at - evaluated_at
    if trip_horizon < timedelta(0):
        raise ValueError("trip_starts_at must not be before evaluated_at")
    if trip_horizon > policy.maximum_vehicle_trip_horizon:
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.TRIP_BEYOND_VEHICLE_HORIZON,
        )
    if vehicle_location is None:
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.VEHICLE_MISSING,
        )
    if vehicle_location.provenance is not LocationProvenance.VEHICLE:
        raise ValueError("vehicle_location must have vehicle provenance")
    if vehicle_location.observed_at is None:
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.VEHICLE_OBSERVATION_TIME_MISSING,
        )

    age = evaluated_at - vehicle_location.observed_at
    if age < timedelta(0):
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.VEHICLE_OBSERVED_IN_FUTURE,
        )
    if age > policy.maximum_vehicle_age:
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.VEHICLE_STALE,
        )
    if vehicle_location.accuracy_m is None:
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.VEHICLE_ACCURACY_UNKNOWN,
        )
    if vehicle_location.accuracy_m > policy.maximum_vehicle_accuracy_m:
        return _fallback_or_unavailable(
            fallback,
            LocationResolutionReason.VEHICLE_INACCURATE,
        )
    return LocationResolution(
        location=vehicle_location.as_resolved(DataQuality.COMPLETE),
        reason=LocationResolutionReason.VEHICLE_ACCEPTED,
    )


def resolve_end_location(
    *,
    policy: EndLocationPolicy,
    primary: LocationCandidate | None,
    fallback: LocationCandidate | None,
) -> LocationResolution:
    """Resolve a destination without ever substituting vehicle position."""

    if primary is not None:
        if primary.provenance not in (
            LocationProvenance.EVENT,
            LocationProvenance.ZONE,
        ):
            raise ValueError("primary destination must have event or zone provenance")
        return LocationResolution(
            location=primary.as_resolved(DataQuality.COMPLETE),
            reason=LocationResolutionReason.PRIMARY_ACCEPTED,
        )
    return _fallback_or_unavailable(
        fallback,
        LocationResolutionReason.PRIMARY_MISSING,
        allowed=policy.allow_configured_fallback,
    )
