from __future__ import annotations

import math
import unittest
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    EndLocationPolicy,
    LocationCandidate,
    LocationProvenance,
    LocationResolutionReason,
    StartLocationPolicy,
    resolve_end_location,
    resolve_start_location,
)

NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
TRIP_START = NOW + timedelta(hours=2)


def candidate(
    provenance: LocationProvenance,
    *,
    observed_at: datetime | None = None,
    accuracy_m: float | None = None,
) -> LocationCandidate:
    return LocationCandidate(
        endpoint_id=f"synthetic:{provenance.value}",
        coordinates=Coordinates(40.0, -10.0),
        provenance=provenance,
        observed_at=observed_at,
        accuracy_m=accuracy_m,
    )


class StartLocationResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = StartLocationPolicy(
            maximum_vehicle_age=timedelta(minutes=15),
            maximum_vehicle_accuracy_m=100.0,
            maximum_vehicle_trip_horizon=timedelta(hours=4),
        )
        self.fallback = candidate(LocationProvenance.CONFIGURED_FALLBACK)

    def test_uses_passive_vehicle_gps_at_inclusive_policy_limits(self) -> None:
        vehicle = candidate(
            LocationProvenance.VEHICLE,
            observed_at=NOW - timedelta(minutes=15),
            accuracy_m=100.0,
        )

        result = resolve_start_location(
            trip_starts_at=NOW + timedelta(hours=4),
            evaluated_at=NOW,
            policy=self.policy,
            vehicle_location=vehicle,
            fallback=self.fallback,
        )

        self.assertEqual(result.reason, LocationResolutionReason.VEHICLE_ACCEPTED)
        self.assertEqual(result.location, vehicle.as_resolved(DataQuality.COMPLETE))
        assert result.location is not None
        self.assertEqual(result.location.quality, DataQuality.COMPLETE)

    def test_falls_back_for_each_unsuitable_vehicle_reason(self) -> None:
        cases = (
            (
                "missing",
                None,
                TRIP_START,
                LocationResolutionReason.VEHICLE_MISSING,
            ),
            (
                "missing observation time",
                candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=None,
                    accuracy_m=10.0,
                ),
                TRIP_START,
                LocationResolutionReason.VEHICLE_OBSERVATION_TIME_MISSING,
            ),
            (
                "stale",
                candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=NOW - timedelta(minutes=16),
                    accuracy_m=10.0,
                ),
                TRIP_START,
                LocationResolutionReason.VEHICLE_STALE,
            ),
            (
                "future observation",
                candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=NOW + timedelta(seconds=1),
                    accuracy_m=10.0,
                ),
                TRIP_START,
                LocationResolutionReason.VEHICLE_OBSERVED_IN_FUTURE,
            ),
            (
                "unknown accuracy",
                candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=NOW,
                    accuracy_m=None,
                ),
                TRIP_START,
                LocationResolutionReason.VEHICLE_ACCURACY_UNKNOWN,
            ),
            (
                "inaccurate",
                candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=NOW,
                    accuracy_m=100.1,
                ),
                TRIP_START,
                LocationResolutionReason.VEHICLE_INACCURATE,
            ),
            (
                "outside trip horizon",
                candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=NOW,
                    accuracy_m=10.0,
                ),
                NOW + timedelta(hours=4, seconds=1),
                LocationResolutionReason.TRIP_BEYOND_VEHICLE_HORIZON,
            ),
        )

        for label, vehicle, trip_start, reason in cases:
            with self.subTest(label=label):
                result = resolve_start_location(
                    trip_starts_at=trip_start,
                    evaluated_at=NOW,
                    policy=self.policy,
                    vehicle_location=vehicle,
                    fallback=self.fallback,
                )
                self.assertEqual(result.reason, reason)
                self.assertEqual(
                    result.location,
                    self.fallback.as_resolved(DataQuality.PARTIAL),
                )
                assert result.location is not None
                self.assertEqual(result.location.quality, DataQuality.PARTIAL)

    def test_is_unavailable_without_acceptable_vehicle_or_fallback(self) -> None:
        result = resolve_start_location(
            trip_starts_at=TRIP_START,
            evaluated_at=NOW,
            policy=self.policy,
            vehicle_location=None,
            fallback=None,
        )

        self.assertIsNone(result.location)
        self.assertEqual(result.quality, DataQuality.UNAVAILABLE)
        self.assertEqual(result.reason, LocationResolutionReason.VEHICLE_MISSING)

    def test_requires_future_trip_and_vehicle_provenance(self) -> None:
        with self.assertRaises(ValueError):
            resolve_start_location(
                trip_starts_at=NOW - timedelta(seconds=1),
                evaluated_at=NOW,
                policy=self.policy,
                vehicle_location=None,
                fallback=None,
            )
        with self.assertRaises(ValueError):
            resolve_start_location(
                trip_starts_at=TRIP_START,
                evaluated_at=NOW,
                policy=self.policy,
                vehicle_location=candidate(
                    LocationProvenance.ZONE,
                    observed_at=NOW,
                    accuracy_m=10.0,
                ),
                fallback=None,
            )


class EndLocationResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = EndLocationPolicy(allow_configured_fallback=True)
        self.fallback = candidate(LocationProvenance.CONFIGURED_FALLBACK)

    def test_accepts_event_or_zone_destination_independently(self) -> None:
        for provenance in (LocationProvenance.EVENT, LocationProvenance.ZONE):
            with self.subTest(provenance=provenance):
                primary = candidate(provenance)
                result = resolve_end_location(
                    policy=self.policy,
                    primary=primary,
                    fallback=self.fallback,
                )
                self.assertEqual(
                    result.location,
                    primary.as_resolved(DataQuality.COMPLETE),
                )
                self.assertEqual(
                    result.reason,
                    LocationResolutionReason.PRIMARY_ACCEPTED,
                )

    def test_uses_explicit_fallback_or_returns_unavailable(self) -> None:
        fallback_result = resolve_end_location(
            policy=self.policy,
            primary=None,
            fallback=self.fallback,
        )
        self.assertEqual(
            fallback_result.location,
            self.fallback.as_resolved(DataQuality.PARTIAL),
        )
        self.assertEqual(
            fallback_result.reason,
            LocationResolutionReason.PRIMARY_MISSING,
        )

        unavailable = resolve_end_location(
            policy=EndLocationPolicy(allow_configured_fallback=False),
            primary=None,
            fallback=self.fallback,
        )
        self.assertIsNone(unavailable.location)
        self.assertEqual(unavailable.quality, DataQuality.UNAVAILABLE)
        self.assertEqual(unavailable.reason, LocationResolutionReason.PRIMARY_MISSING)

    def test_never_substitutes_vehicle_location_for_destination(self) -> None:
        with self.assertRaises(ValueError):
            resolve_end_location(
                policy=self.policy,
                primary=candidate(
                    LocationProvenance.VEHICLE,
                    observed_at=NOW,
                    accuracy_m=10.0,
                ),
                fallback=self.fallback,
            )


class LocationPolicyValidationTests(unittest.TestCase):
    def test_rejects_non_positive_thresholds_and_invalid_accuracy(self) -> None:
        invalid_values = (
            (timedelta(0), 100.0, timedelta(hours=1)),
            (timedelta(minutes=1), 0.0, timedelta(hours=1)),
            (timedelta(minutes=1), math.inf, timedelta(hours=1)),
            (timedelta(minutes=1), 100.0, timedelta(0)),
        )
        for age, accuracy, horizon in invalid_values:
            with self.subTest(age=age, accuracy=accuracy, horizon=horizon):
                with self.assertRaises(ValueError):
                    StartLocationPolicy(age, accuracy, horizon)

    def test_candidate_validates_observation_and_accuracy(self) -> None:
        with self.assertRaises(ValueError):
            candidate(
                LocationProvenance.VEHICLE,
                observed_at=NOW.replace(tzinfo=None),
                accuracy_m=10.0,
            )
        with self.assertRaises(ValueError):
            candidate(
                LocationProvenance.VEHICLE,
                observed_at=NOW,
                accuracy_m=-1.0,
            )


if __name__ == "__main__":
    unittest.main()
