from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.domain.calendar_filters import (
    EventFilterPolicy,
    ExclusionReason,
    classify_event,
    preview_events,
)
from custom_components.mobility_forecast.domain.models import SourceEvent

NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def event(
    event_id: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    location_text: str | None = "Synthetic destination",
    all_day: bool = False,
    is_online: bool = False,
) -> SourceEvent:
    return SourceEvent(
        source_id="calendar.synthetic",
        event_id=event_id,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        all_day=all_day,
        is_online=is_online,
        summary=summary,
        description=description,
        location_text=location_text,
    )


class EventFilterPolicyTests(unittest.TestCase):
    def test_rejects_empty_or_duplicate_normalized_terms(self) -> None:
        for terms in (("",), (" Trip ", "trip")):
            with self.subTest(terms=terms):
                with self.assertRaises(ValueError):
                    EventFilterPolicy(
                        include_terms=terms,
                        exclude_terms=(),
                        allow_online=False,
                        allow_all_day=False,
                        require_location=True,
                    )

    def test_policy_is_immutable(self) -> None:
        policy = EventFilterPolicy((), (), False, False, True)

        with self.assertRaises(FrozenInstanceError):
            policy.allow_online = True  # type: ignore[misc]


class EventClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = EventFilterPolicy(
            include_terms=("client",),
            exclude_terms=("cancelled",),
            allow_online=False,
            allow_all_day=False,
            require_location=True,
        )

    def test_include_terms_match_summary_or_description_case_insensitively(self) -> None:
        for candidate in (
            event("summary", summary="CLIENT visit"),
            event("description", description="Meet the Client"),
        ):
            with self.subTest(event_id=candidate.event_id):
                decision = classify_event(candidate, self.policy)
                self.assertTrue(decision.included)
                self.assertIsNone(decision.exclusion_reason)

    def test_exclude_term_has_precedence_over_include_term(self) -> None:
        decision = classify_event(
            event("excluded", summary="Cancelled client visit"), self.policy
        )

        self.assertFalse(decision.included)
        self.assertEqual(decision.exclusion_reason, ExclusionReason.EXCLUDE_TERM)

    def test_structural_exclusions_are_deterministic(self) -> None:
        cases = (
            (
                event("online", summary="client", is_online=True, location_text=None),
                ExclusionReason.ONLINE,
            ),
            (
                event("all-day", summary="client", all_day=True),
                ExclusionReason.ALL_DAY,
            ),
            (
                event("missing", summary="client", location_text="  "),
                ExclusionReason.MISSING_LOCATION,
            ),
            (
                event("no-match", summary="internal"),
                ExclusionReason.INCLUDE_MISMATCH,
            ),
        )
        for candidate, expected_reason in cases:
            with self.subTest(event_id=candidate.event_id):
                decision = classify_event(candidate, self.policy)
                self.assertFalse(decision.included)
                self.assertEqual(decision.exclusion_reason, expected_reason)

    def test_allowed_online_event_does_not_require_physical_location(self) -> None:
        policy = EventFilterPolicy(
            include_terms=(),
            exclude_terms=(),
            allow_online=True,
            allow_all_day=False,
            require_location=True,
        )

        decision = classify_event(
            event("online", is_online=True, location_text=None), policy
        )

        self.assertTrue(decision.included)


class FilterPreviewTests(unittest.TestCase):
    def test_preview_contains_only_aggregate_counts_in_stable_reason_order(self) -> None:
        private_text = "Confidential Alpha Appointment"
        private_location = "Synthetic Secret Street 99"
        candidates = (
            event("included-private-id", summary=private_text, location_text=private_location),
            event("all-day-private-id", all_day=True),
            event("missing-private-id", location_text=None),
        )
        policy = EventFilterPolicy((), (), False, False, True)

        preview = preview_events(candidates, policy)

        self.assertEqual(preview.total_count, 3)
        self.assertEqual(preview.included_count, 1)
        self.assertEqual(preview.excluded_count, 2)
        self.assertEqual(
            preview.reason_counts,
            (
                (ExclusionReason.ALL_DAY, 1),
                (ExclusionReason.MISSING_LOCATION, 1),
            ),
        )
        rendered = repr(preview)
        for private_value in (
            private_text,
            private_location,
            "included-private-id",
            "all-day-private-id",
            "missing-private-id",
        ):
            self.assertNotIn(private_value, rendered)


if __name__ == "__main__":
    unittest.main()
