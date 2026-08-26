"""Dependency-free domain value objects.

The contracts in this module contain operational inputs, so privacy-sensitive
text and coordinates are intentionally omitted from their representations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_finite_range(
    value: float, field_name: str, minimum: float, maximum: float | None = None
) -> None:
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{field_name} must be finite and at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field_name} must be at most {maximum}")


class DataQuality(StrEnum):
    """Conservative quality state shared by domain outputs."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class LocationProvenance(StrEnum):
    """Source used to resolve an endpoint."""

    EVENT = "event"
    ZONE = "zone"
    VEHICLE = "vehicle"
    CONFIGURED_FALLBACK = "configured_fallback"


@dataclass(frozen=True, slots=True)
class Coordinates:
    """WGS84 coordinates used only as an operational domain input."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        _require_finite_range(self.latitude, "latitude", -90.0, 90.0)
        _require_finite_range(self.longitude, "longitude", -180.0, 180.0)


@dataclass(frozen=True, slots=True)
class SourceEvent:
    """Normalized calendar event supplied to the pure planning pipeline."""

    source_id: str
    event_id: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    is_online: bool
    summary: str | None = field(default=None, repr=False)
    description: str | None = field(default=None, repr=False)
    location_text: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.event_id, "event_id")
        _require_aware(self.starts_at, "starts_at")
        _require_aware(self.ends_at, "ends_at")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    """Resolved endpoint with explicit provenance, age, and quality."""

    endpoint_id: str
    coordinates: Coordinates = field(repr=False)
    provenance: LocationProvenance
    observed_at: datetime | None
    quality: DataQuality

    def __post_init__(self) -> None:
        _require_non_empty(self.endpoint_id, "endpoint_id")
        if self.observed_at is not None:
            _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class Route:
    """Successful directional road route.

    Failures are represented by the separate provider contract and never as a
    zero-valued route. Endpoints stay out of representations because they may
    contain stable identifiers as well as private coordinates.
    """

    origin: ResolvedLocation = field(repr=False)
    destination: ResolvedLocation = field(repr=False)
    distance_m: int
    duration_s: int
    provider: str
    observed_at: datetime
    quality: DataQuality

    def __post_init__(self) -> None:
        if self.distance_m <= 0:
            raise ValueError("distance_m must be positive")
        if self.duration_s <= 0:
            raise ValueError("duration_s must be positive")
        _require_non_empty(self.provider, "provider")
        _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class VehicleObservation:
    """Passive vehicle values; this contract exposes no refresh or action API."""

    observed_at: datetime
    odometer_km: float | None = None
    soc_percent: float | None = None
    estimated_range_km: float | None = None
    location: ResolvedLocation | None = None

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        if self.odometer_km is not None:
            _require_finite_range(self.odometer_km, "odometer_km", 0.0)
        if self.soc_percent is not None:
            _require_finite_range(self.soc_percent, "soc_percent", 0.0, 100.0)
        if self.estimated_range_km is not None:
            _require_finite_range(self.estimated_range_km, "estimated_range_km", 0.0)


@dataclass(frozen=True, slots=True)
class Trip:
    """One planned trip, including explicit degraded-state information."""

    event_id: str
    starts_at: datetime
    origin: ResolvedLocation | None
    destination: ResolvedLocation | None
    route: Route | None
    quality: DataQuality
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.event_id, "event_id")
        _require_aware(self.starts_at, "starts_at")


@dataclass(frozen=True, slots=True)
class Forecast:
    """Daily uncertainty-aware distance and SOC advice."""

    service_date: date
    distance_p50_m: int | None
    distance_p90_m: int | None
    required_soc_p50_percent: float | None
    required_soc_p90_percent: float | None
    quality: DataQuality
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._validate_percentile_pair(
            self.distance_p50_m, self.distance_p90_m, "distance", None
        )
        self._validate_percentile_pair(
            self.required_soc_p50_percent,
            self.required_soc_p90_percent,
            "required_soc",
            100.0,
        )

    @staticmethod
    def _validate_percentile_pair(
        p50: int | float | None,
        p90: int | float | None,
        field_name: str,
        maximum: float | None,
    ) -> None:
        if (p50 is None) != (p90 is None):
            raise ValueError(f"{field_name} percentiles must both be present or absent")
        if p50 is None or p90 is None:
            return
        _require_finite_range(float(p50), f"{field_name}_p50", 0.0, maximum)
        _require_finite_range(float(p90), f"{field_name}_p90", 0.0, maximum)
        if p90 < p50:
            raise ValueError(f"{field_name}_p90 must be at least {field_name}_p50")
