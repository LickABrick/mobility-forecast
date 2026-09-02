from __future__ import annotations

import unittest

from custom_components.mobility_forecast.domain.calendar_filters import (
    EventFilterPolicy,
)
from custom_components.mobility_forecast.profile_config import (
    CONF_ALL_DAY_EVENT_POLICY,
    CONF_END_ANCHOR_ENTITY_ID,
    CONF_NO_LOCATION_EVENT_POLICY,
    CONF_ONLINE_EVENT_POLICY,
    CONF_PHYSICAL_EVENT_POLICY,
    CONF_START_ANCHOR_ENTITY_ID,
    EventHandling,
    ProfilePlanningConfig,
)

SYNTHETIC_CONFIG = {
    CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
    CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
    CONF_PHYSICAL_EVENT_POLICY: "include",
    CONF_ONLINE_EVENT_POLICY: "exclude",
    CONF_ALL_DAY_EVENT_POLICY: "exclude",
    CONF_NO_LOCATION_EVENT_POLICY: "exclude",
}


class ProfilePlanningConfigTests(unittest.TestCase):
    def test_round_trips_independent_anchors_and_explicit_event_policy(self) -> None:
        config = ProfilePlanningConfig.from_entry_data(SYNTHETIC_CONFIG)

        self.assertEqual(config.start_anchor_entity_id, "zone.synthetic_start")
        self.assertEqual(config.end_anchor_entity_id, "zone.synthetic_end")
        self.assertEqual(config.physical_events, EventHandling.INCLUDE)
        self.assertEqual(config.online_events, EventHandling.EXCLUDE)
        self.assertEqual(config.all_day_events, EventHandling.EXCLUDE)
        self.assertEqual(config.events_without_location, EventHandling.EXCLUDE)
        self.assertEqual(config.as_entry_data(), SYNTHETIC_CONFIG)
        self.assertEqual(
            config.event_filter_policy,
            EventFilterPolicy(
                include_terms=(),
                exclude_terms=(),
                allow_physical=True,
                allow_online=False,
                allow_all_day=False,
                require_location=True,
            ),
        )

    def test_all_event_choices_map_without_hidden_boolean_defaults(self) -> None:
        config = ProfilePlanningConfig.from_entry_data(
            {
                **SYNTHETIC_CONFIG,
                CONF_PHYSICAL_EVENT_POLICY: "exclude",
                CONF_ONLINE_EVENT_POLICY: "include",
                CONF_ALL_DAY_EVENT_POLICY: "include",
                CONF_NO_LOCATION_EVENT_POLICY: "include",
            }
        )

        self.assertEqual(
            config.event_filter_policy,
            EventFilterPolicy(
                include_terms=(),
                exclude_terms=(),
                allow_physical=False,
                allow_online=True,
                allow_all_day=True,
                require_location=False,
            ),
        )

    def test_rejects_missing_invalid_or_non_zone_policy_values(self) -> None:
        invalid_cases = (
            {
                key: value
                for key, value in SYNTHETIC_CONFIG.items()
                if key != CONF_END_ANCHOR_ENTITY_ID
            },
            {
                **SYNTHETIC_CONFIG,
                CONF_START_ANCHOR_ENTITY_ID: "device_tracker.synthetic",
            },
            {**SYNTHETIC_CONFIG, CONF_END_ANCHOR_ENTITY_ID: " zone.synthetic_end"},
            {**SYNTHETIC_CONFIG, CONF_ONLINE_EVENT_POLICY: "automatic"},
            {**SYNTHETIC_CONFIG, CONF_ALL_DAY_EVENT_POLICY: True},
        )

        for raw in invalid_cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ProfilePlanningConfig.from_entry_data(raw)

    def test_representation_omits_operational_anchor_identifiers(self) -> None:
        rendered = repr(ProfilePlanningConfig.from_entry_data(SYNTHETIC_CONFIG))

        self.assertNotIn("zone.synthetic_start", rendered)
        self.assertNotIn("zone.synthetic_end", rendered)


if __name__ == "__main__":
    unittest.main()
