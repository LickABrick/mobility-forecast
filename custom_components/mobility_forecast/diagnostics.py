"""Privacy-safe diagnostics projection for the Home Assistant boundary.

This module deliberately accepts only aggregate, typed values. Operational event
text, entity identifiers, addresses, coordinates, provider details, credentials,
and profile names cannot enter the diagnostics snapshot and therefore cannot be
accidentally serialized by this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Final, TypeAlias, cast

from .domain.calendar_filters import FilterPreview
from .domain.models import DataQuality
from .domain.routing import RouteFailureCategory

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .runtime import ProfileRuntimeData

DIAGNOSTICS_SCHEMA_VERSION: Final = 1

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


@dataclass(frozen=True, slots=True)
class DiagnosticsSnapshot:
    """Aggregate coordinator state that is safe to expose to diagnostics."""

    generated_at: datetime
    quality: DataQuality
    filter_preview: FilterPreview
    planned_leg_count: int
    degraded_leg_count: int
    plan_revision_count: int
    training_actual_count: int
    route_cache_entry_count: int
    route_failure_counts: tuple[tuple[RouteFailureCategory, int], ...]

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")

        counts = (
            self.planned_leg_count,
            self.degraded_leg_count,
            self.plan_revision_count,
            self.training_actual_count,
            self.route_cache_entry_count,
        )
        if any(count < 0 for count in counts):
            raise ValueError("diagnostic counts must not be negative")
        if self.degraded_leg_count > self.planned_leg_count:
            raise ValueError("degraded_leg_count must not exceed planned_leg_count")

        categories = tuple(category for category, _ in self.route_failure_counts)
        if len(set(categories)) != len(categories):
            raise ValueError("route failure categories must not be duplicated")
        if any(count <= 0 for _, count in self.route_failure_counts):
            raise ValueError("route failure counts must be positive")


def diagnostics_payload(snapshot: DiagnosticsSnapshot) -> dict[str, JsonValue]:
    """Project one snapshot into a stable JSON-safe allowlisted payload."""

    return {
        "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "generated_at": snapshot.generated_at.isoformat(),
        "quality": snapshot.quality.value,
        "counts": {
            "events_total": snapshot.filter_preview.total_count,
            "events_included": snapshot.filter_preview.included_count,
            "events_excluded": snapshot.filter_preview.excluded_count,
            "planned_legs": snapshot.planned_leg_count,
            "degraded_legs": snapshot.degraded_leg_count,
            "plan_revisions": snapshot.plan_revision_count,
            "training_actuals": snapshot.training_actual_count,
            "route_cache_entries": snapshot.route_cache_entry_count,
        },
        "filter_exclusions": {
            reason.value: count
            for reason, count in snapshot.filter_preview.reason_counts
        },
        "route_failures": {
            category.value: count
            for category, count in snapshot.route_failure_counts
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, JsonValue]:
    """Return only the entry's typed aggregate diagnostics projection.

    Home Assistant entry metadata, configuration, options, and coordinator state
    are deliberately never traversed or serialized by this adapter.
    """

    del hass
    runtime = cast("ProfileRuntimeData", entry.runtime_data)
    snapshot = await runtime.diagnostics_source.read()
    return diagnostics_payload(snapshot)
