from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from custom_components.mobility_forecast.ha_calendar import (
    CalendarSourceConfig,
    CalendarSourceUnavailable,
    HomeAssistantCalendarSource,
    classify_online_event,
)


@dataclass(frozen=True)
class SyntheticCalendarEvent:
    start: date | datetime
    end: date | datetime
    summary: str
    description: str | None = None
    location: str | None = None
    uid: str | None = None
    recurrence_id: str | None = None

    @property
    def all_day(self) -> bool:
        return not isinstance(self.start, datetime)

    @property
    def start_datetime_local(self) -> datetime:
        if isinstance(self.start, datetime):
            return self.start
        return datetime.combine(self.start, time.min, tzinfo=UTC)

    @property
    def end_datetime_local(self) -> datetime:
        if isinstance(self.end, datetime):
            return self.end
        return datetime.combine(self.end, time.min, tzinfo=UTC)


class SyntheticCalendarEntity:
    def __init__(
        self,
        events: list[SyntheticCalendarEvent],
        *,
        read_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.read_error = read_error
        self.calls: list[tuple[object, datetime, datetime]] = []

    async def async_get_events(
        self, hass: object, starts_at: datetime, ends_at: datetime
    ) -> list[SyntheticCalendarEvent]:
        self.calls.append((hass, starts_at, ends_at))
        if self.read_error is not None:
            raise self.read_error
        return list(self.events)


class SyntheticCalendarComponent:
    def __init__(self, entities: dict[str, SyntheticCalendarEntity]) -> None:
        self.entities = entities
        self.lookups: list[str] = []

    def get_entity(self, entity_id: str) -> SyntheticCalendarEntity | None:
        self.lookups.append(entity_id)
        return self.entities.get(entity_id)


class CalendarSourceConfigTests(unittest.TestCase):
    def test_requires_explicit_unique_calendar_entities(self) -> None:
        config = CalendarSourceConfig.from_entry_data(
            {
                "calendar_entity_ids": [
                    "calendar.synthetic_work",
                    "calendar.synthetic_home",
                ]
            }
        )

        self.assertEqual(
            config.entity_ids,
            ("calendar.synthetic_work", "calendar.synthetic_home"),
        )

        invalid_values: tuple[dict[str, Any], ...] = (
            {},
            {"calendar_entity_ids": []},
            {"calendar_entity_ids": ["sensor.synthetic"]},
            {"calendar_entity_ids": ["calendar.Synthetic"]},
            {"calendar_entity_ids": ["calendar.synthetic-name"]},
            {"calendar_entity_ids": [" calendar.synthetic"]},
            {"calendar_entity_ids": ["calendar.synthetic", "calendar.synthetic"]},
            {"calendar_entity_ids": "calendar.synthetic"},
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                CalendarSourceConfig.from_entry_data(value)


class HomeAssistantCalendarSourceTests(unittest.TestCase):
    def test_online_classifier_accepts_only_reviewed_meeting_locations(self) -> None:
        accepted = (
            "https://meet.google.com/synthetic-room",
            "https://tenant.zoom.us/j/123456789",
            "https://teams.microsoft.com/l/meetup-join/synthetic",
            "https://tenant.webex.com/meet/synthetic",
        )

        for location in accepted:
            with self.subTest(location=location):
                self.assertTrue(
                    classify_online_event(
                        SyntheticCalendarEvent(
                            start=datetime(2032, 4, 5, tzinfo=UTC),
                            end=datetime(2032, 4, 5, 1, tzinfo=UTC),
                            summary="Synthetic appointment",
                            location=location,
                            uid="synthetic-online",
                        )
                    )
                )

    def test_online_classifier_rejects_text_urls_and_host_lookalikes(self) -> None:
        rejected = (
            None,
            "",
            "Online meeting",
            "Join at https://meet.google.com/synthetic-room",
            "https://meet.google.com.evil.invalid/synthetic-room",
            "https://maps.google.com/synthetic-place",
            "https://user@meet.google.com/synthetic-room",
            "https://meet.google.com:8443/synthetic-room",
            "https://meet.google.com:invalid/synthetic-room",
        )

        for location in rejected:
            with self.subTest(location=location):
                self.assertFalse(
                    classify_online_event(
                        SyntheticCalendarEvent(
                            start=datetime(2032, 4, 5, tzinfo=UTC),
                            end=datetime(2032, 4, 5, 1, tzinfo=UTC),
                            summary="Synthetic appointment",
                            location=location,
                            uid="synthetic-not-online",
                        )
                    )
                )

    def test_reads_configured_entities_and_normalizes_timed_and_all_day_events(
        self,
    ) -> None:
        starts_at = datetime(2032, 4, 5, 7, 30, tzinfo=UTC)
        ends_at = datetime(2032, 4, 7, 0, 0, tzinfo=UTC)
        work = SyntheticCalendarEntity(
            [
                SyntheticCalendarEvent(
                    start=starts_at,
                    end=datetime(2032, 4, 5, 8, 15, tzinfo=UTC),
                    summary="Synthetic video appointment",
                    description="Synthetic fixture only",
                    location="synthetic-video://room",
                    uid="synthetic-timed",
                    recurrence_id="20320405T073000Z",
                )
            ]
        )
        home = SyntheticCalendarEntity(
            [
                SyntheticCalendarEvent(
                    start=date(2032, 4, 6),
                    end=date(2032, 4, 7),
                    summary="Synthetic all-day event",
                    location="Synthetic destination",
                    uid="synthetic-all-day",
                )
            ]
        )
        component = SyntheticCalendarComponent(
            {
                "calendar.synthetic_work": work,
                "calendar.synthetic_home": home,
            }
        )
        hass = object()
        source = HomeAssistantCalendarSource(
            hass=hass,
            component=component,
            config=CalendarSourceConfig(
                ("calendar.synthetic_work", "calendar.synthetic_home")
            ),
            classify_online=lambda event: event.location == "synthetic-video://room",
        )

        events = asyncio.run(source.async_read(starts_at, ends_at))

        self.assertEqual(component.lookups, list(source.config.entity_ids))
        self.assertEqual(work.calls, [(hass, starts_at, ends_at)])
        self.assertEqual(home.calls, [(hass, starts_at, ends_at)])
        self.assertEqual(
            [(event.source_id, event.event_id) for event in events],
            [
                ("calendar.synthetic_work", "15:synthetic-timed20320405T073000Z"),
                ("calendar.synthetic_home", "synthetic-all-day"),
            ],
        )
        timed, all_day = events
        self.assertTrue(timed.is_online)
        self.assertFalse(timed.all_day)
        self.assertEqual(timed.location_text, "synthetic-video://room")
        self.assertTrue(all_day.all_day)
        self.assertFalse(all_day.is_online)
        self.assertEqual(all_day.starts_at, datetime(2032, 4, 6, tzinfo=UTC))
        self.assertNotIn("Synthetic video appointment", repr(timed))
        self.assertNotIn("Synthetic destination", repr(all_day))

    def test_fails_closed_with_privacy_safe_reasons(self) -> None:
        starts_at = datetime(2032, 4, 5, tzinfo=UTC)
        ends_at = datetime(2032, 4, 6, tzinfo=UTC)
        cases = (
            (
                SyntheticCalendarComponent({}),
                ("calendar.synthetic_missing",),
                "calendar_entity_unavailable",
            ),
            (
                SyntheticCalendarComponent(
                    {
                        "calendar.synthetic": SyntheticCalendarEntity(
                            [
                                SyntheticCalendarEvent(
                                    start=starts_at,
                                    end=ends_at,
                                    summary="Private synthetic summary",
                                    location="Private synthetic location",
                                )
                            ]
                        )
                    }
                ),
                ("calendar.synthetic",),
                "calendar_event_identifier_unavailable",
            ),
        )
        for component, entity_ids, reason in cases:
            with self.subTest(reason=reason):
                source = HomeAssistantCalendarSource(
                    hass=object(),
                    component=component,
                    config=CalendarSourceConfig(entity_ids),
                    classify_online=lambda event: False,
                )
                with self.assertRaises(CalendarSourceUnavailable) as caught:
                    asyncio.run(source.async_read(starts_at, ends_at))
                self.assertEqual(str(caught.exception), reason)
                self.assertNotIn("synthetic", str(caught.exception))
                self.assertNotIn("Private", repr(caught.exception))

    def test_wraps_calendar_read_failures_without_private_error_text(self) -> None:
        starts_at = datetime(2032, 4, 5, tzinfo=UTC)
        ends_at = datetime(2032, 4, 6, tzinfo=UTC)
        entity = SyntheticCalendarEntity(
            [], read_error=RuntimeError("Private synthetic provider response")
        )
        source = HomeAssistantCalendarSource(
            hass=object(),
            component=SyntheticCalendarComponent({"calendar.synthetic": entity}),
            config=CalendarSourceConfig(("calendar.synthetic",)),
            classify_online=lambda event: False,
        )

        with self.assertRaises(CalendarSourceUnavailable) as caught:
            asyncio.run(source.async_read(starts_at, ends_at))

        self.assertEqual(str(caught.exception), "calendar_read_failed")
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertNotIn("Private", repr(caught.exception))

    def test_rejects_invalid_window_before_entity_access(self) -> None:
        component = SyntheticCalendarComponent({})
        source = HomeAssistantCalendarSource(
            hass=object(),
            component=component,
            config=CalendarSourceConfig(("calendar.synthetic",)),
            classify_online=lambda event: False,
        )

        with self.assertRaises(ValueError):
            asyncio.run(
                source.async_read(
                    datetime(2032, 4, 5),
                    datetime(2032, 4, 6),
                )
            )
        with self.assertRaises(ValueError):
            asyncio.run(
                source.async_read(
                    datetime(2032, 4, 6, tzinfo=UTC),
                    datetime(2032, 4, 5, tzinfo=UTC),
                )
            )
        self.assertEqual(component.lookups, [])


if __name__ == "__main__":
    unittest.main()
