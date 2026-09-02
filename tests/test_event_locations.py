from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    DeterministicEventLocationResolver,
    EndLocationPolicy,
    EventLocationFailure,
    EventLocationFailureCategory,
    EventLocationRequest,
    EventLocationResolver,
    EventLocationSuccess,
    LocationProvenance,
    LocationResolutionReason,
    resolve_end_location,
)

NOW = datetime(2033, 2, 3, 9, 0, tzinfo=UTC)


class EventLocationResolverContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = EventLocationRequest(location_text="Synthetic venue 41")
        self.success = EventLocationSuccess(coordinates=Coordinates(42.0, -7.0))

    def test_deterministic_fake_resolves_exact_request_and_composes_destination(
        self,
    ) -> None:
        fake = DeterministicEventLocationResolver({self.request: self.success})
        resolver: EventLocationResolver = fake

        result = asyncio.run(resolver.resolve(self.request))

        self.assertEqual(result, self.success)
        self.assertEqual(fake.requests, (self.request,))
        assert isinstance(result, EventLocationSuccess)
        candidate = result.as_candidate(endpoint_id="event:destination")
        self.assertIs(candidate.provenance, LocationProvenance.EVENT)
        self.assertIsNone(candidate.observed_at)
        self.assertIsNone(candidate.accuracy_m)

        destination = resolve_end_location(
            policy=EndLocationPolicy(allow_configured_fallback=False),
            primary=candidate,
            fallback=None,
        )
        self.assertIs(destination.reason, LocationResolutionReason.PRIMARY_ACCEPTED)
        self.assertIs(destination.quality, DataQuality.COMPLETE)
        assert destination.location is not None
        self.assertEqual(destination.location.coordinates, Coordinates(42.0, -7.0))

    def test_returns_each_typed_privacy_safe_failure_unchanged(self) -> None:
        for category in EventLocationFailureCategory:
            with self.subTest(category=category):
                failure = EventLocationFailure(category=category, occurred_at=NOW)
                resolver = DeterministicEventLocationResolver({self.request: failure})

                result = asyncio.run(resolver.resolve(self.request))

                self.assertEqual(result, failure)
                self.assertEqual(str(failure.category), category.value)

    def test_retryability_is_explicit_and_conservative(self) -> None:
        retryable = {
            EventLocationFailureCategory.RATE_LIMITED,
            EventLocationFailureCategory.TRANSIENT,
        }

        for category in EventLocationFailureCategory:
            with self.subTest(category=category):
                failure = EventLocationFailure(category=category, occurred_at=NOW)
                self.assertEqual(failure.retryable, category in retryable)

    def test_unexpected_fake_request_fails_without_echoing_location_text(self) -> None:
        resolver = DeterministicEventLocationResolver({self.request: self.success})
        unexpected = EventLocationRequest(location_text="Synthetic private place 92")

        with self.assertRaisesRegex(
            AssertionError, "unexpected event-location request"
        ) as caught:
            asyncio.run(resolver.resolve(unexpected))

        self.assertNotIn("Synthetic private place 92", str(caught.exception))

    def test_private_inputs_and_coordinates_are_absent_from_representations(
        self,
    ) -> None:
        request = EventLocationRequest(location_text="Synthetic private venue 73")
        success = EventLocationSuccess(coordinates=Coordinates(-31.25, 118.75))
        candidate = success.as_candidate(endpoint_id="event:destination")
        resolver = DeterministicEventLocationResolver({request: success})

        projection = " ".join(
            (repr(request), repr(success), repr(candidate), repr(resolver))
        )

        self.assertNotIn("Synthetic private venue 73", projection)
        self.assertNotIn("-31.25", projection)
        self.assertNotIn("118.75", projection)

    def test_rejects_blank_inputs_and_naive_failure_time(self) -> None:
        with self.assertRaises(ValueError):
            EventLocationRequest(location_text="  ")
        with self.assertRaises(ValueError):
            self.success.as_candidate(endpoint_id="")
        with self.assertRaises(ValueError):
            EventLocationFailure(
                category=EventLocationFailureCategory.TRANSIENT,
                occurred_at=NOW.replace(tzinfo=None),
            )


if __name__ == "__main__":
    unittest.main()
