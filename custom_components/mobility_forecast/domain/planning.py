"""Pure itinerary assembly and immutable plan revision history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .models import DataQuality, ResolvedLocation, Route, SourceEvent
from .routing import (
    RouteFailure,
    RouteOptions,
    RouteProvider,
    RouteRequest,
    RouteResultSource,
    RouteSuccess,
)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True, slots=True)
class ItineraryCandidate:
    """Filtered event and independently resolved destination.

    Calendar and endpoint identifiers are operational private inputs and are
    intentionally absent from representations.
    """

    event: SourceEvent = field(repr=False)
    deduplication_key: str = field(repr=False)
    destination: ResolvedLocation | None = field(repr=False)
    destination_reason: str

    def __post_init__(self) -> None:
        _require_non_empty(self.deduplication_key, "deduplication_key")
        _require_non_empty(self.destination_reason, "destination_reason")


@dataclass(frozen=True, slots=True)
class PlannedStop:
    """One chronological, deduplicated calendar stop."""

    event_id: str = field(repr=False)
    starts_at: datetime
    ends_at: datetime
    destination: ResolvedLocation | None = field(repr=False)
    destination_reason: str
    source_references: tuple[tuple[str, str], ...] = field(repr=False)

    def __post_init__(self) -> None:
        _require_non_empty(self.event_id, "event_id")
        _require_aware(self.starts_at, "starts_at")
        _require_aware(self.ends_at, "ends_at")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        if not self.source_references:
            raise ValueError("source_references must not be empty")


@dataclass(frozen=True, slots=True)
class PlannedLeg:
    """Directional leg to a stop, including explicit degraded state."""

    stop_index: int
    origin: ResolvedLocation | None = field(repr=False)
    destination: ResolvedLocation | None = field(repr=False)
    route: Route | None
    quality: DataQuality
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.stop_index < 0:
            raise ValueError("stop_index must not be negative")
        if self.route is not None:
            if (
                self.origin != self.route.origin
                or self.destination != self.route.destination
            ):
                raise ValueError("route direction must match leg endpoints")
            if self.quality is DataQuality.UNAVAILABLE:
                raise ValueError("routed leg cannot be unavailable")


@dataclass(frozen=True, slots=True)
class PlanRevision:
    """Immutable result of one plan run; later runs append new revisions."""

    revision_id: str
    service_date: date
    created_at: datetime
    source_observed_at: datetime
    stops: tuple[PlannedStop, ...]
    legs: tuple[PlannedLeg, ...]
    quality: DataQuality
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.revision_id, "revision_id")
        _require_aware(self.created_at, "created_at")
        _require_aware(self.source_observed_at, "source_observed_at")
        if self.source_observed_at > self.created_at:
            raise ValueError("source_observed_at must not be later than created_at")
        if len(self.stops) != len(self.legs):
            raise ValueError("each stop must have exactly one planned leg")
        if any(leg.stop_index != index for index, leg in enumerate(self.legs)):
            raise ValueError("leg indexes must correspond to stop order")
        if not self.stops and self.quality is not DataQuality.UNAVAILABLE:
            raise ValueError("empty plan must be unavailable")


def _deduplicate_candidates(
    candidates: tuple[ItineraryCandidate, ...],
) -> tuple[PlannedStop, ...]:
    groups: dict[str, list[ItineraryCandidate]] = {}
    for candidate in candidates:
        groups.setdefault(candidate.deduplication_key, []).append(candidate)

    stops: list[PlannedStop] = []
    for group in groups.values():
        ordered = sorted(
            group,
            key=lambda item: (item.event.source_id, item.event.event_id),
        )
        canonical = ordered[0]
        for duplicate in ordered[1:]:
            if (
                duplicate.event.starts_at != canonical.event.starts_at
                or duplicate.event.ends_at != canonical.event.ends_at
                or duplicate.destination != canonical.destination
                or duplicate.destination_reason != canonical.destination_reason
            ):
                raise ValueError("deduplication key refers to conflicting candidates")
        stops.append(
            PlannedStop(
                event_id=canonical.event.event_id,
                starts_at=canonical.event.starts_at,
                ends_at=canonical.event.ends_at,
                destination=canonical.destination,
                destination_reason=canonical.destination_reason,
                source_references=tuple(
                    (item.event.source_id, item.event.event_id) for item in ordered
                ),
            )
        )

    return tuple(
        sorted(
            stops,
            key=lambda stop: (
                stop.starts_at,
                stop.ends_at,
                stop.source_references,
            ),
        )
    )


def _successful_leg_quality(
    origin: ResolvedLocation,
    destination: ResolvedLocation,
    success: RouteSuccess,
) -> DataQuality:
    qualities = (origin.quality, destination.quality, success.route.quality)
    if DataQuality.UNAVAILABLE in qualities:
        raise ValueError("resolved routed endpoints cannot be unavailable")
    if DataQuality.PARTIAL in qualities:
        return DataQuality.PARTIAL
    if DataQuality.STALE in qualities:
        return DataQuality.STALE
    return DataQuality.COMPLETE


def _plan_quality(legs: tuple[PlannedLeg, ...]) -> DataQuality:
    if not legs:
        return DataQuality.UNAVAILABLE
    qualities = tuple(leg.quality for leg in legs)
    if DataQuality.UNAVAILABLE in qualities or DataQuality.PARTIAL in qualities:
        return DataQuality.PARTIAL
    if DataQuality.STALE in qualities:
        return DataQuality.STALE
    return DataQuality.COMPLETE


async def assemble_plan_revision(
    *,
    revision_id: str,
    service_date: date,
    created_at: datetime,
    source_observed_at: datetime,
    candidates: tuple[ItineraryCandidate, ...],
    initial_origin: ResolvedLocation | None,
    route_options: RouteOptions,
    route_provider: RouteProvider,
) -> PlanRevision:
    """Deduplicate, order and directionally route one day's candidate stops."""

    _require_non_empty(revision_id, "revision_id")
    _require_aware(created_at, "created_at")
    _require_aware(source_observed_at, "source_observed_at")
    if source_observed_at > created_at:
        raise ValueError("source_observed_at must not be later than created_at")
    for candidate in candidates:
        if candidate.event.starts_at.date() != service_date:
            raise ValueError("candidate start must fall on service_date")

    stops = _deduplicate_candidates(candidates)
    legs: list[PlannedLeg] = []
    origin = initial_origin
    for index, stop in enumerate(stops):
        destination = stop.destination
        if origin is None:
            legs.append(
                PlannedLeg(
                    stop_index=index,
                    origin=None,
                    destination=destination,
                    route=None,
                    quality=DataQuality.UNAVAILABLE,
                    reason_codes=("origin_unavailable",),
                )
            )
        elif destination is None:
            legs.append(
                PlannedLeg(
                    stop_index=index,
                    origin=origin,
                    destination=None,
                    route=None,
                    quality=DataQuality.UNAVAILABLE,
                    reason_codes=(f"destination_{stop.destination_reason}",),
                )
            )
        else:
            request = RouteRequest(origin, destination, route_options, stop.starts_at)
            result = await route_provider.route(request)
            if isinstance(result, RouteFailure):
                legs.append(
                    PlannedLeg(
                        stop_index=index,
                        origin=origin,
                        destination=destination,
                        route=None,
                        quality=DataQuality.PARTIAL,
                        reason_codes=(f"route_{result.category.value}",),
                    )
                )
            else:
                if (
                    result.route.origin != origin
                    or result.route.destination != destination
                ):
                    raise ValueError("route direction does not match planned leg")
                if (
                    result.source is RouteResultSource.PROVIDER
                    and result.route.quality is not DataQuality.COMPLETE
                ):
                    raise ValueError("provider route must have complete quality")
                legs.append(
                    PlannedLeg(
                        stop_index=index,
                        origin=origin,
                        destination=destination,
                        route=result.route,
                        quality=_successful_leg_quality(origin, destination, result),
                    )
                )
        origin = destination

    frozen_legs = tuple(legs)
    reason_codes = ("no_stops",) if not stops else ()
    return PlanRevision(
        revision_id=revision_id,
        service_date=service_date,
        created_at=created_at,
        source_observed_at=source_observed_at,
        stops=stops,
        legs=frozen_legs,
        quality=_plan_quality(frozen_legs),
        reason_codes=reason_codes,
    )


def append_plan_revision(
    history: tuple[PlanRevision, ...], revision: PlanRevision
) -> tuple[PlanRevision, ...]:
    """Append without mutating or replacing historical planning truth."""

    if any(item.revision_id == revision.revision_id for item in history):
        raise ValueError("revision_id already exists")
    if history and revision.created_at <= history[-1].created_at:
        raise ValueError("revision created_at must increase monotonically")
    return (*history, revision)
