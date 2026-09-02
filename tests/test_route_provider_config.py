from __future__ import annotations

import unittest

from custom_components.mobility_forecast.domain.routing import RouteOptions
from custom_components.mobility_forecast.route_provider_config import (
    CONF_HIGHWAY_POLICY,
    CONF_ROUTE_PROVIDER,
    CONF_ROUTE_PROVIDER_API_KEY,
    CONF_TOLL_POLICY,
    ProfileRouteConfig,
    RoutePreference,
    RouteProviderKind,
)

SYNTHETIC_ROUTE_CONFIG = {
    CONF_ROUTE_PROVIDER: "google_routes",
    CONF_ROUTE_PROVIDER_API_KEY: "synthetic-test-key",
    CONF_TOLL_POLICY: "avoid",
    CONF_HIGHWAY_POLICY: "allow",
}


class ProfileRouteConfigTests(unittest.TestCase):
    def test_round_trips_explicit_provider_credential_and_route_choices(self) -> None:
        config = ProfileRouteConfig.from_entry_data(SYNTHETIC_ROUTE_CONFIG)

        self.assertEqual(config.provider, RouteProviderKind.GOOGLE_ROUTES)
        self.assertEqual(config.api_key, "synthetic-test-key")
        self.assertEqual(config.tolls, RoutePreference.AVOID)
        self.assertEqual(config.highways, RoutePreference.ALLOW)
        self.assertEqual(
            config.route_options,
            RouteOptions(avoid_tolls=True, avoid_highways=False),
        )
        self.assertEqual(config.as_entry_data(), SYNTHETIC_ROUTE_CONFIG)

    def test_all_route_preferences_map_without_boolean_defaults(self) -> None:
        config = ProfileRouteConfig.from_entry_data(
            {
                **SYNTHETIC_ROUTE_CONFIG,
                CONF_TOLL_POLICY: "allow",
                CONF_HIGHWAY_POLICY: "avoid",
            }
        )

        self.assertEqual(
            config.route_options,
            RouteOptions(avoid_tolls=False, avoid_highways=True),
        )

    def test_rejects_missing_unknown_or_blank_provider_configuration(self) -> None:
        invalid_cases = (
            {
                key: value
                for key, value in SYNTHETIC_ROUTE_CONFIG.items()
                if key != CONF_ROUTE_PROVIDER
            },
            {**SYNTHETIC_ROUTE_CONFIG, CONF_ROUTE_PROVIDER: "automatic"},
            {**SYNTHETIC_ROUTE_CONFIG, CONF_ROUTE_PROVIDER_API_KEY: ""},
            {**SYNTHETIC_ROUTE_CONFIG, CONF_ROUTE_PROVIDER_API_KEY: " synthetic-key"},
            {**SYNTHETIC_ROUTE_CONFIG, CONF_TOLL_POLICY: "default"},
            {**SYNTHETIC_ROUTE_CONFIG, CONF_HIGHWAY_POLICY: True},
        )

        for raw in invalid_cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ProfileRouteConfig.from_entry_data(raw)

    def test_representation_omits_provider_credential(self) -> None:
        rendered = repr(ProfileRouteConfig.from_entry_data(SYNTHETIC_ROUTE_CONFIG))

        self.assertNotIn("synthetic-test-key", rendered)
        self.assertIn("google_routes", rendered)


if __name__ == "__main__":
    unittest.main()
