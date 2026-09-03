from __future__ import annotations

import unittest
from datetime import timedelta

from custom_components.mobility_forecast.domain.routing import RouteOptions
from custom_components.mobility_forecast.route_provider_config import (
    CONF_GEOCODE_CACHE_RETENTION_HOURS,
    CONF_GEOCODER_BASE_URL,
    CONF_GEOCODER_PROVIDER,
    CONF_HIGHWAY_POLICY,
    CONF_LOCATION_DATA_CONSENT,
    CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH,
    CONF_MAX_REQUEST_ATTEMPTS,
    CONF_MAX_ROUTE_REQUESTS_PER_REFRESH,
    CONF_REQUEST_TIMEOUT_SECONDS,
    CONF_ROUTE_CACHE_FRESH_HOURS,
    CONF_ROUTE_CACHE_STALE_HOURS,
    CONF_ROUTE_PROVIDER,
    CONF_ROUTE_PROVIDER_API_KEY,
    CONF_ROUTING_BASE_URL,
    CONF_TOLL_POLICY,
    GeocoderKind,
    LocationDataConsent,
    ProfileRouteConfig,
    RouteProviderKind,
)

COMMON_POLICY = {
    CONF_LOCATION_DATA_CONSENT: "accepted",
    CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH: 8,
    CONF_MAX_ROUTE_REQUESTS_PER_REFRESH: 16,
    CONF_MAX_REQUEST_ATTEMPTS: 2,
    CONF_REQUEST_TIMEOUT_SECONDS: 10,
    CONF_GEOCODE_CACHE_RETENTION_HOURS: 72,
    CONF_ROUTE_CACHE_FRESH_HOURS: 6,
    CONF_ROUTE_CACHE_STALE_HOURS: 24,
    CONF_TOLL_POLICY: "avoid",
    CONF_HIGHWAY_POLICY: "allow",
}
HOSTED_ORS_CONFIG = {
    CONF_ROUTE_PROVIDER: "openrouteservice_hosted",
    CONF_ROUTE_PROVIDER_API_KEY: "synthetic-test-key",
    **COMMON_POLICY,
}
SELF_HOSTED_ORS_CONFIG = {
    CONF_ROUTE_PROVIDER: "openrouteservice_self_hosted",
    CONF_ROUTING_BASE_URL: "https://routing.synthetic.invalid/ors",
    CONF_GEOCODER_PROVIDER: "photon",
    CONF_GEOCODER_BASE_URL: "https://geocoder.synthetic.invalid/photon",
    **COMMON_POLICY,
}


class ProfileRouteConfigTests(unittest.TestCase):
    def test_hosted_ors_round_trips_one_key_and_discloses_both_recipients(self) -> None:
        config = ProfileRouteConfig.from_entry_data(HOSTED_ORS_CONFIG)

        self.assertEqual(config.provider, RouteProviderKind.OPENROUTESERVICE_HOSTED)
        self.assertEqual(config.api_key, "synthetic-test-key")
        self.assertEqual(config.consent, LocationDataConsent.ACCEPTED)
        self.assertEqual(
            [(item.provider, item.endpoint) for item in config.location_recipients],
            [
                (
                    "OpenRouteService hosted Pelias geocoder",
                    "https://api.heigit.org/geocode/search",
                ),
                (
                    "OpenRouteService hosted routing",
                    "https://api.heigit.org/v2/directions/driving-car",
                ),
            ],
        )
        self.assertEqual(config.as_entry_data(), HOSTED_ORS_CONFIG)

    def test_self_hosted_ors_requires_separate_geocoder_and_endpoints(self) -> None:
        config = ProfileRouteConfig.from_entry_data(SELF_HOSTED_ORS_CONFIG)

        self.assertEqual(
            config.provider, RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED
        )
        self.assertIsNone(config.api_key)
        self.assertEqual(config.geocoder, GeocoderKind.PHOTON)
        self.assertEqual(
            [(item.provider, item.endpoint) for item in config.location_recipients],
            [
                (
                    "Self-hosted Photon geocoder",
                    "https://geocoder.synthetic.invalid/photon",
                ),
                (
                    "Self-hosted OpenRouteService routing",
                    "https://routing.synthetic.invalid/ors",
                ),
            ],
        )
        self.assertEqual(config.as_entry_data(), SELF_HOSTED_ORS_CONFIG)

    def test_optional_hosted_families_have_fixed_separate_recipients(self) -> None:
        cases = (
            (
                "geoapify",
                (
                    (
                        "Geoapify geocoding",
                        "https://api.geoapify.com/v1/geocode/search",
                    ),
                    ("Geoapify routing", "https://api.geoapify.com/v1/routing"),
                ),
            ),
            (
                "google",
                (
                    (
                        "Google Geocoding API",
                        "https://maps.googleapis.com/maps/api/geocode/json",
                    ),
                    (
                        "Google Routes API",
                        "https://routes.googleapis.com/directions/v2:computeRoutes",
                    ),
                ),
            ),
        )

        for provider, expected in cases:
            with self.subTest(provider=provider):
                config = ProfileRouteConfig.from_entry_data(
                    {
                        CONF_ROUTE_PROVIDER: provider,
                        CONF_ROUTE_PROVIDER_API_KEY: "synthetic-test-key",
                        **COMMON_POLICY,
                    }
                )
                self.assertEqual(
                    tuple(
                        (recipient.provider, recipient.endpoint)
                        for recipient in config.location_recipients
                    ),
                    expected,
                )

    def test_projects_explicit_request_and_cache_policies(self) -> None:
        config = ProfileRouteConfig.from_entry_data(HOSTED_ORS_CONFIG)

        self.assertEqual(
            config.route_options,
            RouteOptions(avoid_tolls=True, avoid_highways=False),
        )
        self.assertEqual(config.request_policy.maximum_geocode_requests, 8)
        self.assertEqual(config.request_policy.maximum_route_requests, 16)
        self.assertEqual(config.request_policy.maximum_attempts, 2)
        self.assertEqual(config.request_policy.timeout, timedelta(seconds=10))
        self.assertEqual(config.geocode_cache_policy.maximum_age, timedelta(hours=72))
        self.assertEqual(
            config.route_cache_policy.maximum_fresh_age, timedelta(hours=6)
        )
        self.assertEqual(
            config.route_cache_policy.maximum_stale_age, timedelta(hours=24)
        )

    def test_rejects_missing_consent_unknown_provider_and_unbounded_policy(
        self,
    ) -> None:
        invalid_cases = (
            {
                key: value
                for key, value in HOSTED_ORS_CONFIG.items()
                if key != CONF_ROUTE_PROVIDER
            },
            {**HOSTED_ORS_CONFIG, CONF_ROUTE_PROVIDER: "automatic"},
            {**HOSTED_ORS_CONFIG, CONF_LOCATION_DATA_CONSENT: "declined"},
            {**HOSTED_ORS_CONFIG, CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH: 0},
            {**HOSTED_ORS_CONFIG, CONF_MAX_ROUTE_REQUESTS_PER_REFRESH: 101},
            {**HOSTED_ORS_CONFIG, CONF_MAX_REQUEST_ATTEMPTS: 4},
            {**HOSTED_ORS_CONFIG, CONF_REQUEST_TIMEOUT_SECONDS: 31},
            {**HOSTED_ORS_CONFIG, CONF_GEOCODE_CACHE_RETENTION_HOURS: 721},
            {**HOSTED_ORS_CONFIG, CONF_ROUTE_CACHE_FRESH_HOURS: 25},
            {**HOSTED_ORS_CONFIG, CONF_ROUTE_CACHE_STALE_HOURS: 5},
            {**HOSTED_ORS_CONFIG, CONF_HIGHWAY_POLICY: True},
        )

        for raw in invalid_cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ProfileRouteConfig.from_entry_data(raw)

    def test_rejects_provider_specific_fields_that_are_missing_or_ambiguous(
        self,
    ) -> None:
        invalid_cases = (
            {
                key: value
                for key, value in HOSTED_ORS_CONFIG.items()
                if key != CONF_ROUTE_PROVIDER_API_KEY
            },
            {**HOSTED_ORS_CONFIG, CONF_ROUTE_PROVIDER_API_KEY: " synthetic-key"},
            {**HOSTED_ORS_CONFIG, CONF_ROUTING_BASE_URL: "https://unused.invalid"},
            {
                key: value
                for key, value in SELF_HOSTED_ORS_CONFIG.items()
                if key != CONF_GEOCODER_BASE_URL
            },
            {**SELF_HOSTED_ORS_CONFIG, CONF_GEOCODER_PROVIDER: "automatic"},
            {**SELF_HOSTED_ORS_CONFIG, CONF_ROUTING_BASE_URL: "routing.invalid"},
            {
                **SELF_HOSTED_ORS_CONFIG,
                CONF_GEOCODER_BASE_URL: "https://name:secret@geocoder.invalid",
            },
            {**SELF_HOSTED_ORS_CONFIG, CONF_ROUTE_PROVIDER_API_KEY: "unused"},
        )

        for raw in invalid_cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ProfileRouteConfig.from_entry_data(raw)

    def test_representation_omits_credentials_and_configured_endpoints(self) -> None:
        hosted = repr(ProfileRouteConfig.from_entry_data(HOSTED_ORS_CONFIG))
        self_hosted = repr(ProfileRouteConfig.from_entry_data(SELF_HOSTED_ORS_CONFIG))

        self.assertNotIn("synthetic-test-key", hosted)
        self.assertNotIn("routing.synthetic.invalid", self_hosted)
        self.assertNotIn("geocoder.synthetic.invalid", self_hosted)
        self.assertIn("openrouteservice_hosted", hosted)
        self.assertIn("openrouteservice_self_hosted", self_hosted)


if __name__ == "__main__":
    unittest.main()
