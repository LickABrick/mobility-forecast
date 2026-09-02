"""Privacy-safe resolution of explicitly selected Home Assistant zone anchors.

The adapter reads only latitude and longitude from the two configured local zone
states. Selected entity identifiers and coordinates remain operational values:
they are omitted from adapter/snapshot representations and never enter errors.
There is no geocoder, network provider, service, or entity-write capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, TypeGuard, cast

from .domain.models import (
    Coordinates,
    DataQuality,
    LocationProvenance,
    ResolvedLocation,
)
from .profile_config import ProfilePlanningConfig


class ZoneAnchorFailureReason(StrEnum):
    """Stable private-data-free reason for one configured anchor failure."""

    START_ENTITY_UNAVAILABLE = "start_anchor_entity_unavailable"
    START_COORDINATES_UNAVAILABLE = "start_anchor_coordinates_unavailable"
    START_COORDINATES_INVALID = "start_anchor_coordinates_invalid"
    END_ENTITY_UNAVAILABLE = "end_anchor_entity_unavailable"
    END_COORDINATES_UNAVAILABLE = "end_anchor_coordinates_unavailable"
    END_COORDINATES_INVALID = "end_anchor_coordinates_invalid"


class ZoneAnchorUnavailable(RuntimeError):
    """Fail-closed anchor error containing no entity or coordinate value."""

    def __init__(self, reason: ZoneAnchorFailureReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


class ZoneStateContract(Protocol):
    """Read-only Home Assistant state surface needed by this adapter."""

    @property
    def attributes(self) -> object: ...


class ZoneStateMachineContract(Protocol):
    """Read-only lookup surface for explicitly configured zone states."""

    def get(self, entity_id: str) -> ZoneStateContract | None: ...


class ZoneAnchorResolver(Protocol):
    """Resolve both profile anchors without exposing a service or network path."""

    def resolve(self) -> ConfiguredZoneAnchors:
        """Return both current configured anchors or fail closed."""
        ...


@dataclass(frozen=True, slots=True)
class ConfiguredZoneAnchors:
    """Independent typed start/end endpoints hidden from representations."""

    start: ResolvedLocation = field(repr=False)
    end: ResolvedLocation = field(repr=False)

    def __post_init__(self) -> None:
        for endpoint in (self.start, self.end):
            if endpoint.provenance is not LocationProvenance.ZONE:
                raise ValueError("configured anchors must have zone provenance")
            if endpoint.quality is not DataQuality.COMPLETE:
                raise ValueError("configured anchors must have complete quality")


@dataclass(frozen=True, slots=True)
class HomeAssistantZoneAnchorResolver:
    """Resolve exactly one profile's selected local zone entity states."""

    states: ZoneStateMachineContract = field(repr=False)
    config: ProfilePlanningConfig = field(repr=False)

    def resolve(self) -> ConfiguredZoneAnchors:
        """Read both selected zones and return private typed endpoints."""

        start = self._resolve_one(
            self.config.start_anchor_entity_id,
            endpoint_id="anchor:start",
            entity_failure=ZoneAnchorFailureReason.START_ENTITY_UNAVAILABLE,
            coordinates_missing=ZoneAnchorFailureReason.START_COORDINATES_UNAVAILABLE,
            coordinates_invalid=ZoneAnchorFailureReason.START_COORDINATES_INVALID,
        )
        end = self._resolve_one(
            self.config.end_anchor_entity_id,
            endpoint_id="anchor:end",
            entity_failure=ZoneAnchorFailureReason.END_ENTITY_UNAVAILABLE,
            coordinates_missing=ZoneAnchorFailureReason.END_COORDINATES_UNAVAILABLE,
            coordinates_invalid=ZoneAnchorFailureReason.END_COORDINATES_INVALID,
        )
        return ConfiguredZoneAnchors(start=start, end=end)

    def _resolve_one(
        self,
        entity_id: str,
        *,
        endpoint_id: str,
        entity_failure: ZoneAnchorFailureReason,
        coordinates_missing: ZoneAnchorFailureReason,
        coordinates_invalid: ZoneAnchorFailureReason,
    ) -> ResolvedLocation:
        try:
            state = self.states.get(entity_id)
        except Exception:
            raise ZoneAnchorUnavailable(entity_failure) from None
        if state is None:
            raise ZoneAnchorUnavailable(entity_failure)

        try:
            raw_attributes = state.attributes
        except Exception:
            raise ZoneAnchorUnavailable(coordinates_missing) from None
        if not isinstance(raw_attributes, Mapping):
            raise ZoneAnchorUnavailable(coordinates_missing)
        attributes = cast("Mapping[object, object]", raw_attributes)
        if "latitude" not in attributes or "longitude" not in attributes:
            raise ZoneAnchorUnavailable(coordinates_missing)

        latitude = attributes["latitude"]
        longitude = attributes["longitude"]
        if not _is_coordinate_number(latitude) or not _is_coordinate_number(longitude):
            raise ZoneAnchorUnavailable(coordinates_invalid)
        try:
            coordinates = Coordinates(float(latitude), float(longitude))
        except (TypeError, ValueError, OverflowError):
            raise ZoneAnchorUnavailable(coordinates_invalid) from None
        return ResolvedLocation(
            endpoint_id=endpoint_id,
            coordinates=coordinates,
            provenance=LocationProvenance.ZONE,
            observed_at=None,
            quality=DataQuality.COMPLETE,
        )


def _is_coordinate_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)
