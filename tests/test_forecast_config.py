from __future__ import annotations

import unittest

from custom_components.mobility_forecast.domain.actuals_forecasting import (
    ForecastPolicy,
)
from custom_components.mobility_forecast.forecast_config import ProfileForecastConfig


class ProfileForecastConfigTests(unittest.TestCase):
    def test_requires_and_projects_every_explicit_policy_value(self) -> None:
        data = {
            "minimum_history_samples": 5,
            "minimum_correction_percent": 60,
            "maximum_correction_percent": 180,
            "cold_start_p90_percent": 125,
        }

        config = ProfileForecastConfig.from_entry_data(data)

        self.assertEqual(config.as_entry_data(), data)
        self.assertEqual(
            config.forecast_policy,
            ForecastPolicy(5, 0.6, 1.8, 1.25),
        )

        selector_values = {key: float(value) for key, value in data.items()}
        self.assertEqual(ProfileForecastConfig.from_entry_data(selector_values), config)

    def test_missing_boolean_reversed_and_out_of_range_values_fail_closed(self) -> None:
        valid = {
            "minimum_history_samples": 5,
            "minimum_correction_percent": 60,
            "maximum_correction_percent": 180,
            "cold_start_p90_percent": 125,
        }
        cases = (
            {
                key: value
                for key, value in valid.items()
                if key != "minimum_history_samples"
            },
            {**valid, "minimum_history_samples": True},
            {**valid, "minimum_history_samples": 366},
            {**valid, "minimum_correction_percent": 181},
            {**valid, "cold_start_p90_percent": 99},
            {**valid, "cold_start_p90_percent": 301},
        )
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                ProfileForecastConfig.from_entry_data(data)


if __name__ == "__main__":
    unittest.main()
