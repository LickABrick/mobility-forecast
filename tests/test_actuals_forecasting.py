from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    ActualDistance,
    DataQuality,
    ForecastPolicy,
    OdometerPolicy,
    OdometerSampleReason,
    PlannedLeg,
    PlannedStop,
    PlanRevision,
    Route,
    VehicleObservation,
    build_distance_forecast,
    classify_odometer_sample,
    close_pending_day,
    open_pending_day,
)
from custom_components.mobility_forecast.domain.models import (
    Coordinates,
    LocationProvenance,
    ResolvedLocation,
)

NOW = datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
SERVICE_DATE = date(2026, 1, 15)
ODOMETER_POLICY = OdometerPolicy(
    maximum_sample_age=timedelta(hours=2),
    maximum_daily_distance_km=1_000.0,
)
FORECAST_POLICY = ForecastPolicy(
    minimum_history_samples=3,
    minimum_correction_ratio=0.5,
    maximum_correction_ratio=2.0,
    cold_start_p90_multiplier=1.25,
)


def observation(at: datetime, odometer_km: float | None) -> VehicleObservation:
    return VehicleObservation(observed_at=at, odometer_km=odometer_km)


def revision(
    revision_id: str,
    *,
    created_at: datetime,
    distance_m: int = 20_000,
    quality: DataQuality = DataQuality.COMPLETE,
) -> PlanRevision:
    origin = ResolvedLocation(
        "synthetic:origin",
        Coordinates(40.0, -10.0),
        LocationProvenance.ZONE,
        created_at,
        DataQuality.COMPLETE,
    )
    destination = ResolvedLocation(
        "synthetic:destination",
        Coordinates(41.0, -11.0),
        LocationProvenance.ZONE,
        created_at,
        DataQuality.COMPLETE,
    )
    stop = PlannedStop(
        event_id="synthetic:event",
        starts_at=NOW + timedelta(hours=2),
        ends_at=NOW + timedelta(hours=3),
        destination=destination,
        destination_reason="primary_accepted",
        source_references=(("synthetic:calendar", "synthetic:event"),),
    )
    route = Route(
        origin,
        destination,
        distance_m,
        1_200,
        "deterministic-fake",
        created_at,
        DataQuality.COMPLETE,
    )
    leg = PlannedLeg(0, origin, destination, route, quality)
    return PlanRevision(
        revision_id,
        SERVICE_DATE,
        created_at,
        created_at,
        (stop,),
        (leg,),
        quality,
    )


class OdometerSampleTests(unittest.TestCase):
    def test_classifies_missing_future_stale_and_accepted_samples(self) -> None:
        evaluated_at = NOW + timedelta(hours=2)
        cases = (
            (observation(NOW, None), OdometerSampleReason.MISSING),
            (
                observation(evaluated_at + timedelta(seconds=1), 100.0),
                OdometerSampleReason.FUTURE,
            ),
            (
                observation(NOW - timedelta(seconds=1), 100.0),
                OdometerSampleReason.STALE,
            ),
            (observation(NOW, 100.0), OdometerSampleReason.ACCEPTED),
        )
        for sample, expected in cases:
            with self.subTest(expected=expected):
                result = classify_odometer_sample(sample, evaluated_at, ODOMETER_POLICY)
                self.assertEqual(result.reason, expected)
                self.assertEqual(
                    result.quality,
                    DataQuality.COMPLETE
                    if expected is OdometerSampleReason.ACCEPTED
                    else DataQuality.UNAVAILABLE,
                )

    def test_policy_requires_positive_explicit_limits(self) -> None:
        with self.assertRaises(ValueError):
            OdometerPolicy(timedelta(0), 1_000.0)
        with self.assertRaises(ValueError):
            OdometerPolicy(timedelta(hours=1), 0.0)


class PendingDayTests(unittest.TestCase):
    def test_closes_against_revision_captured_when_day_opened(self) -> None:
        first = revision("revision:original", created_at=NOW - timedelta(hours=2))
        later_edit = revision(
            "revision:later-edit",
            created_at=NOW + timedelta(minutes=30),
            distance_m=40_000,
        )
        pending = open_pending_day(
            revisions=(first, later_edit),
            service_date=SERVICE_DATE,
            opened_at=NOW,
            start_observation=observation(NOW, 1_000.0),
            policy=ODOMETER_POLICY,
        )

        self.assertEqual(pending.revision_id, "revision:original")
        self.assertEqual(pending.planned_distance_m, 20_000)
        actual = close_pending_day(
            pending,
            end_observation=observation(NOW + timedelta(hours=1), 1_022.0),
            closed_at=NOW + timedelta(hours=1),
            policy=ODOMETER_POLICY,
        )

        self.assertEqual(actual.revision_id, "revision:original")
        self.assertEqual(actual.actual_distance_m, 22_000)
        self.assertEqual(actual.quality, DataQuality.COMPLETE)
        with self.assertRaises(FrozenInstanceError):
            pending.revision_id = "changed"  # type: ignore[misc]

    def test_rejects_no_current_revision_and_incomplete_planned_distance(self) -> None:
        future = revision("revision:future", created_at=NOW + timedelta(seconds=1))
        with self.assertRaises(ValueError):
            open_pending_day(
                (future,),
                SERVICE_DATE,
                NOW,
                observation(NOW, 1_000.0),
                ODOMETER_POLICY,
            )

        degraded = revision(
            "revision:partial",
            created_at=NOW - timedelta(hours=1),
            quality=DataQuality.PARTIAL,
        )
        with self.assertRaises(ValueError):
            open_pending_day(
                (degraded,),
                SERVICE_DATE,
                NOW,
                observation(NOW, 1_000.0),
                ODOMETER_POLICY,
            )

    def test_rejects_rollback_excessive_distance_and_stale_end_sample(self) -> None:
        pending = open_pending_day(
            (revision("revision:1", created_at=NOW - timedelta(hours=1)),),
            SERVICE_DATE,
            NOW,
            observation(NOW, 1_000.0),
            ODOMETER_POLICY,
        )
        for sample, closed_at in (
            (observation(NOW + timedelta(hours=1), 999.0), NOW + timedelta(hours=1)),
            (observation(NOW + timedelta(hours=1), 2_001.0), NOW + timedelta(hours=1)),
            (observation(NOW, 1_020.0), NOW + timedelta(hours=3)),
        ):
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                close_pending_day(pending, sample, closed_at, ODOMETER_POLICY)


class RobustForecastTests(unittest.TestCase):
    def actual(self, revision_id: str, planned_m: int, actual_m: int) -> ActualDistance:
        return ActualDistance(
            service_date=SERVICE_DATE - timedelta(days=int(revision_id)),
            revision_id=f"revision:{revision_id}",
            planned_distance_m=planned_m,
            actual_distance_m=actual_m,
            closed_at=NOW,
            quality=DataQuality.COMPLETE,
        )

    def test_cold_start_uses_uncorrected_p50_and_explicit_p90_margin(self) -> None:
        forecast = build_distance_forecast(
            revision("revision:target", created_at=NOW - timedelta(hours=1)),
            actuals=(),
            policy=FORECAST_POLICY,
        )

        self.assertEqual(forecast.distance_p50_m, 20_000)
        self.assertEqual(forecast.distance_p90_m, 25_000)
        self.assertEqual(forecast.quality, DataQuality.PARTIAL)
        self.assertEqual(forecast.reason_codes, ("cold_start",))

    def test_uses_median_and_nearest_rank_p90_after_rejecting_outliers(self) -> None:
        actuals = (
            self.actual("1", 10_000, 10_000),
            self.actual("2", 10_000, 11_000),
            self.actual("3", 10_000, 12_000),
            self.actual("4", 10_000, 100_000),
        )
        forecast = build_distance_forecast(
            revision("revision:target", created_at=NOW - timedelta(hours=1)),
            actuals,
            FORECAST_POLICY,
        )

        self.assertEqual(forecast.distance_p50_m, 22_000)
        self.assertEqual(forecast.distance_p90_m, 24_000)
        self.assertEqual(forecast.quality, DataQuality.COMPLETE)
        self.assertEqual(forecast.reason_codes, ("outliers_excluded",))

    def test_remains_cold_start_when_too_few_inlier_samples_remain(self) -> None:
        actuals = (
            self.actual("1", 10_000, 10_000),
            self.actual("2", 10_000, 100_000),
            self.actual("3", 10_000, 100_000),
        )
        forecast = build_distance_forecast(
            revision("revision:target", created_at=NOW - timedelta(hours=1)),
            actuals,
            FORECAST_POLICY,
        )

        self.assertEqual(forecast.distance_p50_m, 20_000)
        self.assertEqual(forecast.distance_p90_m, 25_000)
        self.assertEqual(
            forecast.reason_codes,
            ("cold_start", "outliers_excluded"),
        )

    def test_rejects_duplicate_or_nonhistorical_training_actuals(self) -> None:
        historical = self.actual("1", 10_000, 10_000)
        target = revision("revision:target", created_at=NOW - timedelta(hours=1))
        with self.assertRaises(ValueError):
            build_distance_forecast(
                target,
                (historical, historical),
                FORECAST_POLICY,
            )

        nonhistorical = ActualDistance(
            service_date=SERVICE_DATE,
            revision_id="revision:same-day",
            planned_distance_m=10_000,
            actual_distance_m=10_000,
            closed_at=NOW,
            quality=DataQuality.COMPLETE,
        )
        with self.assertRaises(ValueError):
            build_distance_forecast(target, (nonhistorical,), FORECAST_POLICY)

    def test_unavailable_plan_never_becomes_zero_distance(self) -> None:
        empty = PlanRevision(
            "revision:empty",
            SERVICE_DATE,
            NOW,
            NOW,
            (),
            (),
            DataQuality.UNAVAILABLE,
            ("no_stops",),
        )
        forecast = build_distance_forecast(empty, (), FORECAST_POLICY)

        self.assertIsNone(forecast.distance_p50_m)
        self.assertIsNone(forecast.distance_p90_m)
        self.assertEqual(forecast.quality, DataQuality.UNAVAILABLE)
        self.assertEqual(forecast.reason_codes, ("planned_distance_unavailable",))


if __name__ == "__main__":
    unittest.main()
