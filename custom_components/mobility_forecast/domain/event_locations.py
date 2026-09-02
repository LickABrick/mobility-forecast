"""Provider-neutral event-location resolution with deterministic fakes.

Location text and coordinates are operational private inputs. They are omitted
from representations, while failures expose only stable categories and times.
This module contains no provider adapter, cache, credential, or network path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from .location_resolution import LocationCandidate
from .models import Coordinates, LocationProvenance


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class EventLocationRequest:
    """Minimal geocoding input with private location text hidden from repr."""

    location_text: str = field(repr=False)

    def __post_init__(self) -> None:
        _require_non_empty(self.location_text, "location_text")


class EventLocationFailureCategory(StrEnum):
    """Stable provider-neutral event-location failure categories."""

    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    TRANSIENT = "transient"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EventLocationFailure:
    """Privacy-safe failure without provider text or request data."""

    category: EventLocationFailureCategory
    occurred_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.occurred_at, "occurred_at")

    @property
    def retryable(self) -> bool:
        """Return whether a later retry may reasonably succeed."""

        return self.category in (
            EventLocationFailureCategory.RATE_LIMITED,
            EventLocationFailureCategory.TRANSIENT,
        )


@dataclass(frozen=True, slots=True)
class EventLocationSuccess:
    """Resolved coordinates with private values hidden from representations."""

    coordinates: Coordinates = field(repr=False)

    def as_candidate(self, endpoint_id: str) -> LocationCandidate:
        """Build an event-provenance candidate using a caller-owned opaque ID."""

        _require_non_empty(endpoint_id, "endpoint_id")
        return LocationCandidate(
            endpoint_id=endpoint_id,
            coordinates=self.coordinates,
            provenance=LocationProvenance.EVENT,
            observed_at=None,
            accuracy_m=None,
        )


type EventLocationResult = EventLocationSuccess | EventLocationFailure


class EventLocationResolver(Protocol):
    """Asynchronous read-only boundary for resolving physical location text."""

    async def resolve(self, request: EventLocationRequest) -> EventLocationResult:
        """Resolve one location without exposing event content beyond its location."""
        ...


class DeterministicEventLocationResolver:
    """Exact in-memory resolver fake that cannot perform network access."""

    def __init__(
        self,
        responses: Mapping[EventLocationRequest, EventLocationResult],
    ) -> None:
        self._responses = dict(responses)
        self._requests: list[EventLocationRequest] = []

    @property
    def requests(self) -> tuple[EventLocationRequest, ...]:
        """Return the exact requests received by the fake."""

        return tuple(self._requests)

    async def resolve(self, request: EventLocationRequest) -> EventLocationResult:
        self._requests.append(request)
        try:
            return self._responses[request]
        except KeyError as error:
            raise AssertionError("unexpected event-location request") from error
