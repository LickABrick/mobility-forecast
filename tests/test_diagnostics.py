from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from custom_components.mobility_forecast.diagnostics import (
    DIAGNOSTICS_SCHEMA_VERSION,
    DiagnosticsSnapshot,
    diagnostics_payload,
)
from custom_components.mobility_forecast.domain import DataQuality
from custom_components.mobility_forecast.domain.calendar_filters import (
    ExclusionReason,
    FilterPreview,
)
from custom_components.mobility_forecast.domain.routing import RouteFailureCategory

NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


class DiagnosticsTests(unittest.TestCase):
    def test_emits_only_versioned_aggregate_privacy_safe_data(self) -> None:
        snapshot = DiagnosticsSnapshot(
            generated_at=NOW,
            quality=DataQuality.PARTIAL,
            filter_preview=FilterPreview(
                total_count=5,
                included_count=2,
                excluded_count=3,
                reason_counts=(
                    (ExclusionReason.ONLINE, 1),
                    (ExclusionReason.MISSING_LOCATION, 2),
                ),
            ),
            planned_leg_count=2,
            degraded_leg_count=1,
            plan_revision_count=4,
            training_actual_count=3,
            route_cache_entry_count=2,
            route_failure_counts=((RouteFailureCategory.TRANSIENT, 1),),
        )

        payload = diagnostics_payload(snapshot)

        self.assertEqual(
            payload,
            {
                "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
                "generated_at": "2026-01-15T08:00:00+00:00",
                "quality": "partial",
                "counts": {
                    "events_total": 5,
                    "events_included": 2,
                    "events_excluded": 3,
                    "planned_legs": 2,
                    "degraded_legs": 1,
                    "plan_revisions": 4,
                    "training_actuals": 3,
                    "route_cache_entries": 2,
                },
                "filter_exclusions": {
                    "online": 1,
                    "missing_location": 2,
                },
                "route_failures": {"transient": 1},
            },
        )
        self.assertEqual(json.loads(json.dumps(payload)), payload)
        rendered = json.dumps(payload)
        for forbidden_key in (
            "profile_name",
            "entity_id",
            "event_id",
            "summary",
            "description",
            "address",
            "latitude",
            "longitude",
            "provider",
            "credential",
            "token",
        ):
            self.assertNotIn(forbidden_key, rendered)

    def test_snapshot_is_immutable_and_rejects_invalid_counts(self) -> None:
        preview = FilterPreview(0, 0, 0, ())
        snapshot = DiagnosticsSnapshot(
            generated_at=NOW,
            quality=DataQuality.COMPLETE,
            filter_preview=preview,
            planned_leg_count=0,
            degraded_leg_count=0,
            plan_revision_count=0,
            training_actual_count=0,
            route_cache_entry_count=0,
            route_failure_counts=(),
        )
        with self.assertRaises(FrozenInstanceError):
            snapshot.quality = DataQuality.PARTIAL  # type: ignore[misc]

        base = {
            "generated_at": NOW,
            "quality": DataQuality.PARTIAL,
            "filter_preview": preview,
            "planned_leg_count": 1,
            "degraded_leg_count": 0,
            "plan_revision_count": 0,
            "training_actual_count": 0,
            "route_cache_entry_count": 0,
            "route_failure_counts": (),
        }
        for field in (
            "planned_leg_count",
            "degraded_leg_count",
            "plan_revision_count",
            "training_actual_count",
            "route_cache_entry_count",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                DiagnosticsSnapshot(**(base | {field: -1}))

        with self.assertRaises(ValueError):
            DiagnosticsSnapshot(**(base | {"degraded_leg_count": 2}))
        with self.assertRaises(ValueError):
            DiagnosticsSnapshot(
                **(
                    base
                    | {
                        "route_failure_counts": (
                            (RouteFailureCategory.TRANSIENT, 1),
                            (RouteFailureCategory.TRANSIENT, 2),
                        )
                    }
                )
            )
        with self.assertRaises(ValueError):
            DiagnosticsSnapshot(
                **(
                    base
                    | {"route_failure_counts": ((RouteFailureCategory.UNAVAILABLE, 0),)}
                )
            )

    def test_rejects_naive_generation_time(self) -> None:
        with self.assertRaises(ValueError):
            DiagnosticsSnapshot(
                generated_at=NOW.replace(tzinfo=None),
                quality=DataQuality.UNAVAILABLE,
                filter_preview=FilterPreview(0, 0, 0, ()),
                planned_leg_count=0,
                degraded_leg_count=0,
                plan_revision_count=0,
                training_actual_count=0,
                route_cache_entry_count=0,
                route_failure_counts=(),
            )


if __name__ == "__main__":
    unittest.main()
