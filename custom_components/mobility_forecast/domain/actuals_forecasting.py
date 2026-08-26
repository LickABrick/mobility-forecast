"""Passive odometer actuals and a robust distance-forecast baseline.

All policy limits are explicit domain inputs. This module has no Home Assistant,
vehicle refresh, storage, or network boundary.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from .models import DataQuality, Forecast, VehicleObservation
from .planning import PlanRevision


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_positive_finite(value: float, field_name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


@dataclass(frozen=True, slots=True)
class OdometerPolicy:
    """Required limits for accepting passive odometer observations."""

    maximum_sample_age: timedelta
    maximum_daily_distance_km: float

    def __post_init__(self) -> None:
        if self.maximum_sample_age <= timedelta(0):
            raise ValueError("maximum_sample_age must be positive")
        _require_positive_finite(
            self.maximum_daily_distance_km, "maximum_daily_distance_km"
        )


class OdometerSampleReason(StrEnum):
    """Privacy-safe result of validating one passive sample."""

    ACCEPTED = "accepted"
    MISSING = "missing"
    FUTURE = "future"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class OdometerSampleAssessment:
    """Validated sample result without vehicle or location details."""

    reason: OdometerSampleReason
    quality: DataQuality
    observed_at: datetime
    odometer_km: float | None

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        if self.reason is OdometerSampleReason.ACCEPTED:
            if self.quality is not DataQuality.COMPLETE or self.odometer_km is None:
                raise ValueError(
                    "accepted sample must contain a complete odometer value"
                )
        elif self.quality is not DataQuality.UNAVAILABLE:
            raise ValueError("rejected sample must be unavailable")


@dataclass(frozen=True, slots=True)
class PendingDay:
    """Historical plan snapshot waiting for a passive closing sample."""

    service_date: date
    revision_id: str
    planned_distance_m: int
    opened_at: datetime
    start_observed_at: datetime
    start_odometer_km: float

    def __post_init__(self) -> None:
        if not self.revision_id.strip():
            raise ValueError("revision_id must not be empty")
        if self.planned_distance_m <= 0:
            raise ValueError("planned_distance_m must be positive")
        _require_aware(self.opened_at, "opened_at")
        _require_aware(self.start_observed_at, "start_observed_at")
        if self.start_observed_at > self.opened_at:
            raise ValueError("start sample must not be future-dated")
        if not math.isfinite(self.start_odometer_km) or self.start_odometer_km < 0:
            raise ValueError("start_odometer_km must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ActualDistance:
    """Closed actual bound permanently to its captured plan revision."""

    service_date: date
    revision_id: str
    planned_distance_m: int
    actual_distance_m: int
    closed_at: datetime
    quality: DataQuality

    def __post_init__(self) -> None:
        if not self.revision_id.strip():
            raise ValueError("revision_id must not be empty")
        if self.planned_distance_m <= 0:
            raise ValueError("planned_distance_m must be positive")
        if self.actual_distance_m < 0:
            raise ValueError("actual_distance_m must not be negative")
        _require_aware(self.closed_at, "closed_at")
        if self.quality is not DataQuality.COMPLETE:
            raise ValueError("closed training actual must be complete")


@dataclass(frozen=True, slots=True)
class ForecastPolicy:
    """Explicit cold-start and robust correction policy."""

    minimum_history_samples: int
    minimum_correction_ratio: float
    maximum_correction_ratio: float
    cold_start_p90_multiplier: float

    def __post_init__(self) -> None:
        if self.minimum_history_samples <= 0:
            raise ValueError("minimum_history_samples must be positive")
        _require_positive_finite(
            self.minimum_correction_ratio, "minimum_correction_ratio"
        )
        _require_positive_finite(
            self.maximum_correction_ratio, "maximum_correction_ratio"
        )
        _require_positive_finite(
            self.cold_start_p90_multiplier, "cold_start_p90_multiplier"
        )
        if self.maximum_correction_ratio < self.minimum_correction_ratio:
            raise ValueError(
                "maximum_correction_ratio must be at least minimum_correction_ratio"
            )
        if self.cold_start_p90_multiplier < 1.0:
            raise ValueError("cold_start_p90_multiplier must be at least one")


def classify_odometer_sample(
    observation: VehicleObservation,
    evaluated_at: datetime,
    policy: OdometerPolicy,
) -> OdometerSampleAssessment:
    """Classify a passively supplied sample using inclusive age limits."""

    _require_aware(evaluated_at, "evaluated_at")
    if observation.odometer_km is None:
        reason = OdometerSampleReason.MISSING
    elif observation.observed_at > evaluated_at:
        reason = OdometerSampleReason.FUTURE
    elif evaluated_at - observation.observed_at > policy.maximum_sample_age:
        reason = OdometerSampleReason.STALE
    else:
        reason = OdometerSampleReason.ACCEPTED
    return OdometerSampleAssessment(
        reason=reason,
        quality=(
            DataQuality.COMPLETE
            if reason is OdometerSampleReason.ACCEPTED
            else DataQuality.UNAVAILABLE
        ),
        observed_at=observation.observed_at,
        odometer_km=(
            observation.odometer_km if reason is OdometerSampleReason.ACCEPTED else None
        ),
    )


def _complete_planned_distance(revision: PlanRevision) -> int | None:
    if revision.quality is not DataQuality.COMPLETE or not revision.legs:
        return None
    routes = tuple(leg.route for leg in revision.legs)
    if any(route is None for route in routes):
        return None
    return sum(route.distance_m for route in routes if route is not None)


def open_pending_day(
    revisions: tuple[PlanRevision, ...],
    service_date: date,
    opened_at: datetime,
    start_observation: VehicleObservation,
    policy: OdometerPolicy,
) -> PendingDay:
    """Capture the latest revision that existed when the actual period opened."""

    _require_aware(opened_at, "opened_at")
    current = tuple(
        revision
        for revision in revisions
        if revision.service_date == service_date and revision.created_at <= opened_at
    )
    if not current:
        raise ValueError("no plan revision was current when the day opened")
    selected = max(current, key=lambda revision: revision.created_at)
    planned_distance_m = _complete_planned_distance(selected)
    if planned_distance_m is None:
        raise ValueError("current plan has no complete planned distance")
    assessment = classify_odometer_sample(start_observation, opened_at, policy)
    if assessment.odometer_km is None:
        raise ValueError(f"start odometer sample rejected: {assessment.reason.value}")
    return PendingDay(
        service_date=service_date,
        revision_id=selected.revision_id,
        planned_distance_m=planned_distance_m,
        opened_at=opened_at,
        start_observed_at=assessment.observed_at,
        start_odometer_km=assessment.odometer_km,
    )


def close_pending_day(
    pending: PendingDay,
    end_observation: VehicleObservation,
    closed_at: datetime,
    policy: OdometerPolicy,
) -> ActualDistance:
    """Close one pending period without consulting later plan revisions."""

    _require_aware(closed_at, "closed_at")
    if closed_at <= pending.opened_at:
        raise ValueError("closed_at must be later than opened_at")
    assessment = classify_odometer_sample(end_observation, closed_at, policy)
    if assessment.odometer_km is None:
        raise ValueError(f"end odometer sample rejected: {assessment.reason.value}")
    if assessment.observed_at <= pending.start_observed_at:
        raise ValueError("end sample must be newer than start sample")
    travelled_km = assessment.odometer_km - pending.start_odometer_km
    if travelled_km < 0:
        raise ValueError("odometer rollback cannot close a pending day")
    if travelled_km > policy.maximum_daily_distance_km:
        raise ValueError("actual distance exceeds maximum_daily_distance_km")
    return ActualDistance(
        service_date=pending.service_date,
        revision_id=pending.revision_id,
        planned_distance_m=pending.planned_distance_m,
        actual_distance_m=round(travelled_km * 1_000),
        closed_at=closed_at,
        quality=DataQuality.COMPLETE,
    )


def _nearest_rank(values: tuple[float, ...], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def build_distance_forecast(
    revision: PlanRevision,
    actuals: tuple[ActualDistance, ...],
    policy: ForecastPolicy,
) -> Forecast:
    """Apply bounded historical correction ratios to one complete plan.

    Ratios outside the explicit policy bounds are excluded. Median correction
    resists skew, and nearest-rank P90 remains conservative for small samples.
    Until enough inliers exist, the plan is returned as P50 with the explicit
    cold-start P90 multiplier.
    """

    revision_ids = tuple(actual.revision_id for actual in actuals)
    if len(set(revision_ids)) != len(revision_ids):
        raise ValueError("training actual revision identifiers must be unique")
    if any(actual.service_date >= revision.service_date for actual in actuals):
        raise ValueError("training actuals must predate the forecast service date")

    planned_distance_m = _complete_planned_distance(revision)
    if planned_distance_m is None:
        return Forecast(
            service_date=revision.service_date,
            distance_p50_m=None,
            distance_p90_m=None,
            required_soc_p50_percent=None,
            required_soc_p90_percent=None,
            quality=DataQuality.UNAVAILABLE,
            reason_codes=("planned_distance_unavailable",),
        )

    ratios = tuple(
        actual.actual_distance_m / actual.planned_distance_m
        for actual in actuals
        if actual.quality is DataQuality.COMPLETE
    )
    inliers = tuple(
        ratio
        for ratio in ratios
        if policy.minimum_correction_ratio <= ratio <= policy.maximum_correction_ratio
    )
    excluded = len(inliers) != len(ratios)
    if len(inliers) < policy.minimum_history_samples:
        reasons = ("cold_start",)
        if excluded:
            reasons += ("outliers_excluded",)
        return Forecast(
            service_date=revision.service_date,
            distance_p50_m=planned_distance_m,
            distance_p90_m=math.ceil(
                planned_distance_m * policy.cold_start_p90_multiplier
            ),
            required_soc_p50_percent=None,
            required_soc_p90_percent=None,
            quality=DataQuality.PARTIAL,
            reason_codes=reasons,
        )

    p50_ratio = float(statistics.median(inliers))
    p90_ratio = max(p50_ratio, _nearest_rank(inliers, 0.9))
    return Forecast(
        service_date=revision.service_date,
        distance_p50_m=math.ceil(planned_distance_m * p50_ratio),
        distance_p90_m=math.ceil(planned_distance_m * p90_ratio),
        required_soc_p50_percent=None,
        required_soc_p90_percent=None,
        quality=DataQuality.COMPLETE,
        reason_codes=("outliers_excluded",) if excluded else (),
    )
