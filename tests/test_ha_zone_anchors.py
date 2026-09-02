from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from custom_components.mobility_forecast.domain import DataQuality, LocationProvenance
from custom_components.mobility_forecast.ha_zone_anchors import (
    ConfiguredZoneAnchors,
    HomeAssistantZoneAnchorResolver,
    ZoneAnchorFailureReason,
    ZoneAnchorUnavailable,
)
from custom_components.mobility_forecast.profile_config import (
    EventHandling,
    ProfilePlanningConfig,
)


@dataclass(frozen=True)
class SyntheticState:
    attributes: object


class SyntheticStates:
    def __init__(self, states: dict[str, SyntheticState]) -> None:
        self.states = states
        self.lookups: list[str] = []

    def get(self, entity_id: str) -> SyntheticState | None:
        self.lookups.append(entity_id)
        return self.states.get(entity_id)


def planning_config() -> ProfilePlanningConfig:
    return ProfilePlanningConfig(
        start_anchor_entity_id="zone.synthetic_start",
        end_anchor_entity_id="zone.synthetic_end",
        physical_events=EventHandling.INCLUDE,
        online_events=EventHandling.EXCLUDE,
        all_day_events=EventHandling.EXCLUDE,
        events_without_location=EventHandling.EXCLUDE,
    )


class HomeAssistantZoneAnchorResolverTests(unittest.TestCase):
    def test_resolves_only_selected_zones_to_private_typed_endpoints(self) -> None:
        states = SyntheticStates(
            {
                "zone.synthetic_start": SyntheticState(
                    {
                        "latitude": 12.5,
                        "longitude": -34.25,
                        "friendly_name": "Synthetic private start label",
                    }
                ),
                "zone.synthetic_end": SyntheticState(
                    {"latitude": -20, "longitude": 40}
                ),
                "zone.synthetic_unselected": SyntheticState(
                    {"latitude": 1.0, "longitude": 2.0}
                ),
            }
        )
        resolver = HomeAssistantZoneAnchorResolver(states, planning_config())

        anchors = resolver.resolve()

        self.assertIsInstance(anchors, ConfiguredZoneAnchors)
        self.assertEqual(states.lookups, ["zone.synthetic_start", "zone.synthetic_end"])
        self.assertEqual(anchors.start.endpoint_id, "anchor:start")
        self.assertEqual(anchors.end.endpoint_id, "anchor:end")
        self.assertEqual(anchors.start.coordinates.latitude, 12.5)
        self.assertEqual(anchors.start.coordinates.longitude, -34.25)
        self.assertEqual(anchors.end.coordinates.latitude, -20.0)
        self.assertEqual(anchors.end.coordinates.longitude, 40.0)
        for endpoint in (anchors.start, anchors.end):
            self.assertIs(endpoint.provenance, LocationProvenance.ZONE)
            self.assertIs(endpoint.quality, DataQuality.COMPLETE)
            self.assertIsNone(endpoint.observed_at)

        projection = repr(anchors)
        self.assertNotIn("zone.synthetic", projection)
        self.assertNotIn("12.5", projection)
        self.assertNotIn("-34.25", projection)
        self.assertNotIn("Synthetic private", projection)
        self.assertNotIn("zone.synthetic", repr(resolver))

    def test_missing_zone_fails_closed_with_role_specific_safe_reason(self) -> None:
        cases: tuple[tuple[dict[str, SyntheticState], ZoneAnchorFailureReason], ...] = (
            ({}, ZoneAnchorFailureReason.START_ENTITY_UNAVAILABLE),
            (
                {
                    "zone.synthetic_start": SyntheticState(
                        {"latitude": 12.5, "longitude": -34.25}
                    )
                },
                ZoneAnchorFailureReason.END_ENTITY_UNAVAILABLE,
            ),
        )

        for states_by_id, reason in cases:
            with self.subTest(reason=reason):
                resolver = HomeAssistantZoneAnchorResolver(
                    SyntheticStates(states_by_id), planning_config()
                )
                with self.assertRaises(ZoneAnchorUnavailable) as caught:
                    resolver.resolve()
                self.assertIs(caught.exception.reason, reason)
                self.assertEqual(str(caught.exception), reason.value)
                self.assertNotIn("synthetic", repr(caught.exception))

    def test_missing_or_malformed_coordinates_never_create_an_endpoint(self) -> None:
        invalid_attributes: tuple[tuple[object, ZoneAnchorFailureReason], ...] = (
            ({"longitude": 5.0}, ZoneAnchorFailureReason.START_COORDINATES_UNAVAILABLE),
            (
                {"latitude": 5.0},
                ZoneAnchorFailureReason.START_COORDINATES_UNAVAILABLE,
            ),
            ([], ZoneAnchorFailureReason.START_COORDINATES_UNAVAILABLE),
            (
                {"latitude": "5.0", "longitude": 6.0},
                ZoneAnchorFailureReason.START_COORDINATES_INVALID,
            ),
            (
                {"latitude": True, "longitude": 6.0},
                ZoneAnchorFailureReason.START_COORDINATES_INVALID,
            ),
            (
                {"latitude": 91.0, "longitude": 6.0},
                ZoneAnchorFailureReason.START_COORDINATES_INVALID,
            ),
        )

        for attributes, reason in invalid_attributes:
            with self.subTest(attributes=attributes):
                states = SyntheticStates(
                    {
                        "zone.synthetic_start": SyntheticState(attributes),
                        "zone.synthetic_end": SyntheticState(
                            {"latitude": 1.0, "longitude": 2.0}
                        ),
                    }
                )
                resolver = HomeAssistantZoneAnchorResolver(states, planning_config())
                with self.assertRaises(ZoneAnchorUnavailable) as caught:
                    resolver.resolve()
                self.assertIs(caught.exception.reason, reason)

    def test_end_coordinate_failure_is_independent_from_valid_start(self) -> None:
        private_value: Any = object()
        states = SyntheticStates(
            {
                "zone.synthetic_start": SyntheticState(
                    {"latitude": 12.5, "longitude": -34.25}
                ),
                "zone.synthetic_end": SyntheticState(
                    {"latitude": private_value, "longitude": 40.0}
                ),
            }
        )
        resolver = HomeAssistantZoneAnchorResolver(states, planning_config())

        with self.assertRaises(ZoneAnchorUnavailable) as caught:
            resolver.resolve()

        self.assertIs(
            caught.exception.reason,
            ZoneAnchorFailureReason.END_COORDINATES_INVALID,
        )
        self.assertEqual(states.lookups, ["zone.synthetic_start", "zone.synthetic_end"])
        self.assertNotIn(repr(private_value), repr(caught.exception))


if __name__ == "__main__":
    unittest.main()
