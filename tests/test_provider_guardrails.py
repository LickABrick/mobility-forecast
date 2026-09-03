from __future__ import annotations

import unittest
from datetime import timedelta

from custom_components.mobility_forecast.provider_guardrails import (
    MAX_GEOCODE_REQUESTS_PER_REFRESH,
    MAX_REQUEST_ATTEMPTS,
    MAX_REQUEST_TIMEOUT,
    MAX_ROUTE_REQUESTS_PER_REFRESH,
    GeocodeCachePolicy,
    ProviderRequestPolicy,
    build_geocode_cache_key,
)


class ProviderRequestPolicyTests(unittest.TestCase):
    def test_hard_budgets_and_retry_boundaries_are_inclusive(self) -> None:
        policy = ProviderRequestPolicy(
            maximum_geocode_requests=MAX_GEOCODE_REQUESTS_PER_REFRESH,
            maximum_route_requests=MAX_ROUTE_REQUESTS_PER_REFRESH,
            maximum_attempts=MAX_REQUEST_ATTEMPTS,
            timeout=MAX_REQUEST_TIMEOUT,
        )

        self.assertTrue(policy.can_start_geocode(completed_requests=0))
        self.assertFalse(
            policy.can_start_geocode(
                completed_requests=MAX_GEOCODE_REQUESTS_PER_REFRESH
            )
        )
        self.assertTrue(policy.can_start_route(completed_requests=0))
        self.assertFalse(
            policy.can_start_route(completed_requests=MAX_ROUTE_REQUESTS_PER_REFRESH)
        )
        self.assertTrue(policy.can_retry(failed_attempt=1, retryable=True))
        self.assertFalse(
            policy.can_retry(failed_attempt=MAX_REQUEST_ATTEMPTS, retryable=True)
        )
        self.assertFalse(policy.can_retry(failed_attempt=1, retryable=False))

    def test_rejects_nonpositive_over_limit_or_fractional_values(self) -> None:
        invalid_cases = (
            (MAX_GEOCODE_REQUESTS_PER_REFRESH + 1, 1, 1, timedelta(seconds=1)),
            (1, MAX_ROUTE_REQUESTS_PER_REFRESH + 1, 1, timedelta(seconds=1)),
            (1, 1, MAX_REQUEST_ATTEMPTS + 1, timedelta(seconds=1)),
            (1, 1, 1, MAX_REQUEST_TIMEOUT + timedelta(seconds=1)),
            (0, 1, 1, timedelta(seconds=1)),
            (1.5, 1, 1, timedelta(seconds=1)),
        )

        for geocodes, routes, attempts, timeout in invalid_cases:
            with (
                self.subTest(values=(geocodes, routes, attempts, timeout)),
                self.assertRaises(ValueError),
            ):
                ProviderRequestPolicy(  # type: ignore[arg-type]
                    geocodes, routes, attempts, timeout
                )

        policy = ProviderRequestPolicy(1, 1, 1, timedelta(seconds=1))
        with self.assertRaises(ValueError):
            policy.can_start_geocode(completed_requests=0.5)  # type: ignore[arg-type]


class GeocodeCachePrivacyTests(unittest.TestCase):
    def test_cache_key_is_profile_keyed_provider_specific_and_content_opaque(
        self,
    ) -> None:
        private_location = "Synthetic Private Place 42"
        first = build_geocode_cache_key(
            private_location,
            privacy_key=b"first-profile-key-material",
            provider_namespace="synthetic-provider:v1",
        )
        repeated = build_geocode_cache_key(
            private_location,
            privacy_key=b"first-profile-key-material",
            provider_namespace="synthetic-provider:v1",
        )
        other_profile = build_geocode_cache_key(
            private_location,
            privacy_key=b"other-profile-key-material",
            provider_namespace="synthetic-provider:v1",
        )
        other_provider = build_geocode_cache_key(
            private_location,
            privacy_key=b"first-profile-key-material",
            provider_namespace="other-provider:v1",
        )

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, other_profile)
        self.assertNotEqual(first, other_provider)
        self.assertNotIn(private_location, repr(first))
        self.assertEqual(len(first.digest), 64)

    def test_cache_retention_is_positive_and_hard_bounded(self) -> None:
        self.assertEqual(
            GeocodeCachePolicy(timedelta(hours=720)).maximum_age,
            timedelta(hours=720),
        )
        for maximum_age in (timedelta(0), timedelta(hours=721)):
            with self.subTest(maximum_age=maximum_age), self.assertRaises(ValueError):
                GeocodeCachePolicy(maximum_age)


if __name__ == "__main__":
    unittest.main()
