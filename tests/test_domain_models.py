from __future__ import annotations

import math
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    Forecast,
    LocationProvenance,
    ResolvedLocation,
    Route,
    SourceEvent,
    Trip,
    VehicleObservation,
)

NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


class CoordinatesTests(unittest.TestCase):
    def test_accepts_boundary_coordinates(self) -> None:
        self.assertEqual(Coordinates(-90.0, 180.0).latitude, -90.0)

    def test_rejects_invalid_or_non_finite_coordinates(self) -> None:
        for latitude, longitude in (
            (90.1, 0.0),
            (0.0, -180.1),
            (math.nan, 0.0),
            (0.0, math.inf),
        ):
            with self.subTest(latitude=latitude, longitude=longitude):
                with self.assertRaises(ValueError):
                    Coordinates(latitude, longitude)


class SourceEventTests(unittest.TestCase):
    def test_is_immutable_and_hides_private_text_from_repr(self) -> None:
        event = SourceEvent(
            source_id="calendar.synthetic",
            event_id="event-1",
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
            summary="Private appointment",
            description="Private details",
            location_text="Synthetic Street 1",
        )

        rendered = repr(event)
        self.assertNotIn("Private appointment", rendered)
        self.assertNotIn("Private details", rendered)
        self.assertNotIn("Synthetic Street 1", rendered)
        with self.assertRaises(FrozenInstanceError):
            event.event_id = "changed"  # type: ignore[misc]

    def test_rejects_naive_or_reversed_times(self) -> None:
        with self.assertRaises(ValueError):
            SourceEvent("calendar.synthetic", "event-1", NOW.replace(tzinfo=None), NOW)
        with self.assertRaises(ValueError):
            SourceEvent("calendar.synthetic", "event-1", NOW, NOW)


class MobilityValueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.origin = ResolvedLocation(
            endpoint_id="zone.synthetic_home",
            coordinates=Coordinates(52.0, 5.0),
            provenance=LocationProvenance.ZONE,
            observed_at=NOW,
            quality=DataQuality.COMPLETE,
        )
        self.destination = ResolvedLocation(
            endpoint_id="event:event-1",
            coordinates=Coordinates(52.1, 5.1),
            provenance=LocationProvenance.EVENT,
            observed_at=NOW,
            quality=DataQuality.COMPLETE,
        )

    def test_location_repr_hides_coordinates(self) -> None:
        rendered = repr(self.origin)
        self.assertNotIn("52.0", rendered)
        self.assertNotIn("5.0", rendered)

    def test_route_requires_positive_measurements_and_aware_time(self) -> None:
        route = Route(
            origin=self.origin,
            destination=self.destination,
            distance_m=12_000,
            duration_s=1_200,
            provider="deterministic-fake",
            observed_at=NOW,
            quality=DataQuality.COMPLETE,
        )
        self.assertEqual(route.distance_m, 12_000)

        for distance_m, duration_s in ((0, 1), (1, 0), (-1, 1)):
            with self.subTest(distance_m=distance_m, duration_s=duration_s):
                with self.assertRaises(ValueError):
                    Route(
                        self.origin,
                        self.destination,
                        distance_m,
                        duration_s,
                        "deterministic-fake",
                        NOW,
                        DataQuality.COMPLETE,
                    )

    def test_vehicle_observation_validates_optional_values(self) -> None:
        observation = VehicleObservation(
            observed_at=NOW,
            odometer_km=12_345.6,
            soc_percent=55.0,
            estimated_range_km=210.0,
            location=self.origin,
        )
        self.assertEqual(observation.soc_percent, 55.0)

        for field, value in (
            ("odometer_km", -1.0),
            ("soc_percent", 100.1),
            ("estimated_range_km", math.nan),
        ):
            kwargs = {"observed_at": NOW, field: value}
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    VehicleObservation(**kwargs)  # type: ignore[arg-type]

    def test_trip_can_represent_partial_without_fabricating_route(self) -> None:
        trip = Trip(
            event_id="event-1",
            starts_at=NOW,
            origin=self.origin,
            destination=None,
            route=None,
            quality=DataQuality.PARTIAL,
            reason_codes=("destination_unresolved",),
        )
        self.assertIsNone(trip.route)
        self.assertEqual(trip.quality, DataQuality.PARTIAL)

    def test_forecast_preserves_uncertainty_order_and_unavailable_state(self) -> None:
        forecast = Forecast(
            service_date=date(2026, 1, 15),
            distance_p50_m=20_000,
            distance_p90_m=26_000,
            required_soc_p50_percent=20.0,
            required_soc_p90_percent=27.0,
            quality=DataQuality.COMPLETE,
        )
        self.assertEqual(forecast.distance_p90_m, 26_000)

        unavailable = Forecast(
            service_date=date(2026, 1, 16),
            distance_p50_m=None,
            distance_p90_m=None,
            required_soc_p50_percent=None,
            required_soc_p90_percent=None,
            quality=DataQuality.UNAVAILABLE,
            reason_codes=("route_unavailable",),
        )
        self.assertIsNone(unavailable.distance_p50_m)

        with self.assertRaises(ValueError):
            Forecast(
                date(2026, 1, 15),
                30_000,
                20_000,
                30.0,
                20.0,
                DataQuality.COMPLETE,
            )


if __name__ == "__main__":
    unittest.main()
