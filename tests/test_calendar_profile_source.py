from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.calendar_profile_source import (
    CalendarIngestionProfileSource,
)
from custom_components.mobility_forecast.domain.calendar_filters import (
    EventFilterPolicy,
)
from custom_components.mobility_forecast.ha_calendar import (
    CalendarSourceConfig,
    HomeAssistantCalendarSource,
    classify_online_event,
)
from custom_components.mobility_forecast.ha_zone_anchors import (
    HomeAssistantZoneAnchorResolver,
    ZoneAnchorFailureReason,
    ZoneAnchorUnavailable,
)
from custom_components.mobility_forecast.profile_config import (
    EventHandling,
    ProfilePlanningConfig,
)
from custom_components.mobility_forecast.storage import ProfileState
from tests.test_ha_calendar_source import (
    SyntheticCalendarComponent,
    SyntheticCalendarEntity,
    SyntheticCalendarEvent,
)
from tests.test_ha_zone_anchors import SyntheticState, SyntheticStates

NOW = datetime(2032, 4, 5, 7, 0, tzinfo=UTC)
EMPTY_STATE = ProfileState(revisions=(), pending_days=(), actuals=())
ALLOW_ALL_EVENTS = EventFilterPolicy((), (), True, True, True, False)


def zone_anchor_resolver(
    *, include_end: bool = True
) -> HomeAssistantZoneAnchorResolver:
    states = {
        "zone.synthetic_start": SyntheticState({"latitude": 12.5, "longitude": -34.25})
    }
    if include_end:
        states["zone.synthetic_end"] = SyntheticState(
            {"latitude": -20.0, "longitude": 40.0}
        )
    return HomeAssistantZoneAnchorResolver(
        SyntheticStates(states),
        ProfilePlanningConfig(
            start_anchor_entity_id="zone.synthetic_start",
            end_anchor_entity_id="zone.synthetic_end",
            physical_events=EventHandling.INCLUDE,
            online_events=EventHandling.EXCLUDE,
            all_day_events=EventHandling.EXCLUDE,
            events_without_location=EventHandling.EXCLUDE,
        ),
    )


class CalendarIngestionProfileSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_exact_bounded_window_and_projects_only_dates(self) -> None:
        private_summary = "Synthetic private appointment text"
        private_location = "Synthetic private destination text"
        entity = SyntheticCalendarEntity(
            [
                SyntheticCalendarEvent(
                    start=NOW + timedelta(hours=2),
                    end=NOW + timedelta(hours=3),
                    summary=private_summary,
                    location=private_location,
                    uid="synthetic-one",
                ),
                SyntheticCalendarEvent(
                    start=NOW + timedelta(days=2),
                    end=NOW + timedelta(days=2, hours=1),
                    summary="Another synthetic private appointment",
                    uid="synthetic-two",
                ),
            ]
        )
        hass = object()
        calendar_source = HomeAssistantCalendarSource(
            hass=hass,
            component=SyntheticCalendarComponent({"calendar.synthetic": entity}),
            config=CalendarSourceConfig(("calendar.synthetic",)),
            classify_online=lambda event: False,
        )
        source = CalendarIngestionProfileSource(
            calendar_source=calendar_source,
            zone_anchor_resolver=zone_anchor_resolver(),
            event_filter_policy=ALLOW_ALL_EVENTS,
            now=lambda: NOW,
            horizon=timedelta(days=7),
        )

        update = await source.read(EMPTY_STATE)

        self.assertEqual(entity.calls, [(hass, NOW, NOW + timedelta(days=7))])
        self.assertIs(update.state, EMPTY_STATE)
        self.assertEqual(
            tuple(item.service_date.isoformat() for item in update.forecasts),
            ("2032-04-05", "2032-04-07"),
        )
        for forecast in update.forecasts:
            self.assertIsNone(forecast.distance_p50_m)
            self.assertIsNone(forecast.distance_p90_m)
            self.assertEqual(forecast.quality.value, "unavailable")
            self.assertEqual(forecast.reason_codes, ("forecast_pipeline_unconfigured",))
        projection = repr(update)
        self.assertNotIn(private_summary, projection)
        self.assertNotIn(private_location, projection)
        self.assertNotIn("calendar.synthetic", projection)

    async def test_empty_calendar_publishes_successful_empty_snapshot(self) -> None:
        entity = SyntheticCalendarEntity([])
        source = CalendarIngestionProfileSource(
            calendar_source=HomeAssistantCalendarSource(
                hass=object(),
                component=SyntheticCalendarComponent({"calendar.synthetic": entity}),
                config=CalendarSourceConfig(("calendar.synthetic",)),
                classify_online=lambda event: False,
            ),
            zone_anchor_resolver=zone_anchor_resolver(),
            event_filter_policy=ALLOW_ALL_EVENTS,
            now=lambda: NOW,
            horizon=timedelta(days=1),
        )

        update = await source.read(EMPTY_STATE)

        self.assertEqual(update.forecasts, ())
        self.assertEqual(update.generated_at, NOW)

    def test_requires_positive_horizon(self) -> None:
        calendar_source = HomeAssistantCalendarSource(
            hass=object(),
            component=SyntheticCalendarComponent({}),
            config=CalendarSourceConfig(("calendar.synthetic",)),
            classify_online=lambda event: False,
        )
        with self.assertRaises(ValueError):
            CalendarIngestionProfileSource(
                calendar_source=calendar_source,
                zone_anchor_resolver=zone_anchor_resolver(),
                event_filter_policy=ALLOW_ALL_EVENTS,
                now=lambda: NOW,
                horizon=timedelta(0),
            )

    async def test_anchor_failure_stops_before_calendar_and_remains_safe(self) -> None:
        entity = SyntheticCalendarEntity([])
        source = CalendarIngestionProfileSource(
            calendar_source=HomeAssistantCalendarSource(
                hass=object(),
                component=SyntheticCalendarComponent({"calendar.synthetic": entity}),
                config=CalendarSourceConfig(("calendar.synthetic",)),
                classify_online=lambda event: False,
            ),
            zone_anchor_resolver=zone_anchor_resolver(include_end=False),
            event_filter_policy=ALLOW_ALL_EVENTS,
            now=lambda: NOW,
            horizon=timedelta(days=1),
        )

        with self.assertRaises(ZoneAnchorUnavailable) as caught:
            await source.read(EMPTY_STATE)

        self.assertIs(
            caught.exception.reason,
            ZoneAnchorFailureReason.END_ENTITY_UNAVAILABLE,
        )
        self.assertEqual(entity.calls, [])
        self.assertNotIn("synthetic", repr(caught.exception))

    async def test_applies_stored_structural_policy_before_projecting_dates(
        self,
    ) -> None:
        entity = SyntheticCalendarEntity(
            [
                SyntheticCalendarEvent(
                    start=NOW + timedelta(hours=1),
                    end=NOW + timedelta(hours=2),
                    summary="Synthetic physical appointment",
                    location="Synthetic destination",
                    uid="synthetic-physical",
                ),
                SyntheticCalendarEvent(
                    start=NOW + timedelta(days=1),
                    end=NOW + timedelta(days=1, hours=1),
                    summary="Synthetic online appointment",
                    location="https://meet.google.com/synthetic-room",
                    uid="synthetic-online",
                ),
                SyntheticCalendarEvent(
                    start=(NOW + timedelta(days=2)).date(),
                    end=(NOW + timedelta(days=3)).date(),
                    summary="Synthetic all-day appointment",
                    location="Synthetic destination",
                    uid="synthetic-all-day",
                ),
                SyntheticCalendarEvent(
                    start=NOW + timedelta(days=3),
                    end=NOW + timedelta(days=3, hours=1),
                    summary="Synthetic no-location appointment",
                    uid="synthetic-no-location",
                ),
            ]
        )
        source = CalendarIngestionProfileSource(
            calendar_source=HomeAssistantCalendarSource(
                hass=object(),
                component=SyntheticCalendarComponent({"calendar.synthetic": entity}),
                config=CalendarSourceConfig(("calendar.synthetic",)),
                classify_online=classify_online_event,
            ),
            zone_anchor_resolver=zone_anchor_resolver(),
            event_filter_policy=EventFilterPolicy((), (), True, False, False, True),
            now=lambda: NOW,
            horizon=timedelta(days=7),
        )

        update = await source.read(EMPTY_STATE)

        self.assertEqual(
            tuple(forecast.service_date for forecast in update.forecasts),
            (NOW.date(),),
        )
        self.assertIsNone(update.forecasts[0].distance_p90_m)
        self.assertEqual(update.forecasts[0].quality.value, "unavailable")


if __name__ == "__main__":
    unittest.main()
