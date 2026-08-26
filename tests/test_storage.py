from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    ActualDistance,
    Coordinates,
    DataQuality,
    LocationProvenance,
    PendingDay,
    PlannedLeg,
    PlannedStop,
    PlanRevision,
    ResolvedLocation,
    Route,
)
from custom_components.mobility_forecast.storage import (
    STORAGE_SCHEMA_VERSION,
    ProfileState,
    decode_profile_state,
    encode_profile_state,
    profile_storage_key,
)

NOW = datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
SERVICE_DATE = date(2026, 1, 15)


def revision() -> PlanRevision:
    origin = ResolvedLocation(
        endpoint_id="synthetic:origin",
        coordinates=Coordinates(40.0, -10.0),
        provenance=LocationProvenance.ZONE,
        observed_at=NOW - timedelta(minutes=5),
        quality=DataQuality.COMPLETE,
    )
    destination = ResolvedLocation(
        endpoint_id="synthetic:destination",
        coordinates=Coordinates(41.0, -11.0),
        provenance=LocationProvenance.EVENT,
        observed_at=None,
        quality=DataQuality.PARTIAL,
    )
    stop = PlannedStop(
        event_id="synthetic:event",
        starts_at=NOW + timedelta(hours=2),
        ends_at=NOW + timedelta(hours=3),
        destination=destination,
        destination_reason="event_accepted",
        source_references=(("synthetic:calendar", "synthetic:event"),),
    )
    route = Route(
        origin=origin,
        destination=destination,
        distance_m=12_345,
        duration_s=1_234,
        provider="deterministic-fake",
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )
    leg = PlannedLeg(
        stop_index=0,
        origin=origin,
        destination=destination,
        route=route,
        quality=DataQuality.PARTIAL,
        reason_codes=("destination_partial",),
    )
    return PlanRevision(
        revision_id="revision:synthetic",
        service_date=SERVICE_DATE,
        created_at=NOW,
        source_observed_at=NOW - timedelta(minutes=1),
        stops=(stop,),
        legs=(leg,),
        quality=DataQuality.PARTIAL,
        reason_codes=("destination_partial",),
    )


def state() -> ProfileState:
    pending = PendingDay(
        service_date=SERVICE_DATE,
        revision_id="revision:synthetic",
        planned_distance_m=12_345,
        opened_at=NOW + timedelta(hours=1),
        start_observed_at=NOW + timedelta(minutes=55),
        start_odometer_km=1_000.5,
    )
    actual = ActualDistance(
        service_date=SERVICE_DATE - timedelta(days=1),
        revision_id="revision:historical",
        planned_distance_m=10_000,
        actual_distance_m=11_000,
        closed_at=NOW - timedelta(hours=1),
        quality=DataQuality.COMPLETE,
    )
    return ProfileState(
        revisions=(revision(),), pending_days=(pending,), actuals=(actual,)
    )


class ProfileStorageTests(unittest.TestCase):
    def test_round_trips_versioned_json_safe_state_without_mutability(self) -> None:
        original = state()

        encoded = encode_profile_state(original)
        serialized = json.dumps(encoded, sort_keys=True)
        restored = decode_profile_state(json.loads(serialized))

        self.assertEqual(encoded["version"], STORAGE_SCHEMA_VERSION)
        self.assertEqual(restored, original)
        self.assertIsInstance(restored.revisions, tuple)
        self.assertIsInstance(restored.revisions[0].stops, tuple)
        self.assertIsInstance(restored.revisions[0].legs, tuple)
        with self.assertRaises(FrozenInstanceError):
            restored.actuals = ()  # type: ignore[misc]

    def test_preserves_unavailable_leg_without_fabricating_route_values(self) -> None:
        empty = PlanRevision(
            revision_id="revision:empty",
            service_date=SERVICE_DATE,
            created_at=NOW,
            source_observed_at=NOW,
            stops=(),
            legs=(),
            quality=DataQuality.UNAVAILABLE,
            reason_codes=("no_stops",),
        )

        restored = decode_profile_state(
            encode_profile_state(ProfileState((empty,), (), ()))
        )

        self.assertEqual(restored.revisions[0], empty)
        self.assertEqual(restored.revisions[0].legs, ())
        self.assertEqual(restored.revisions[0].quality, DataQuality.UNAVAILABLE)

    def test_storage_keys_are_entry_scoped_and_never_use_profile_titles(self) -> None:
        first = profile_storage_key("entry-synthetic-a")
        second = profile_storage_key("entry-synthetic-b")

        self.assertNotEqual(first, second)
        self.assertEqual(first, "mobility_forecast.entry-synthetic-a")
        self.assertNotIn("My commute", first)
        with self.assertRaises(ValueError):
            profile_storage_key("  ")

    def test_rejects_unknown_versions_and_malformed_nested_values(self) -> None:
        encoded = encode_profile_state(state())
        newer = {**encoded, "version": STORAGE_SCHEMA_VERSION + 1}
        malformed = json.loads(json.dumps(encoded))
        malformed["revisions"][0]["legs"][0]["route"]["distance_m"] = 0

        with self.assertRaisesRegex(ValueError, "unsupported storage schema version"):
            decode_profile_state(newer)
        with self.assertRaises(ValueError):
            decode_profile_state(malformed)

    def test_rejects_duplicate_state_records(self) -> None:
        item = state()
        with self.assertRaisesRegex(ValueError, "revision identifiers"):
            ProfileState((item.revisions[0], item.revisions[0]), (), ())
        with self.assertRaisesRegex(ValueError, "pending service dates"):
            ProfileState((), (item.pending_days[0], item.pending_days[0]), ())
        with self.assertRaisesRegex(ValueError, "actual revision identifiers"):
            ProfileState((), (), (item.actuals[0], item.actuals[0]))


if __name__ == "__main__":
    unittest.main()
