from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    DeterministicEventLocationResolver,
    DeterministicRouteProvider,
    EventFilterPolicy,
    EventLocationFailure,
    EventLocationFailureCategory,
    EventLocationRequest,
    EventLocationSuccess,
    ForecastPolicy,
    LocationProvenance,
    ResolvedLocation,
    Route,
    RouteFailure,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteSuccess,
)
from custom_components.mobility_forecast.ha_calendar import (
    CalendarSourceConfig,
    HomeAssistantCalendarSource,
)
from custom_components.mobility_forecast.routed_profile_source import (
    RoutedCalendarProfileSource,
)
from custom_components.mobility_forecast.storage import ProfileState
from tests.synthetic_pipeline import (
    SyntheticCalendarComponent,
    SyntheticCalendarEntity,
    SyntheticCalendarEvent,
)
from tests.test_calendar_profile_source import zone_anchor_resolver

NOW = datetime(2035, 3, 4, 7, 0, tzinfo=UTC)
START = NOW + timedelta(hours=2)
EMPTY_STATE = ProfileState((), (), ())
OPTIONS = RouteOptions(avoid_tolls=True, avoid_highways=False)
FORECAST_POLICY = ForecastPolicy(3, 0.5, 2.0, 1.25)
FILTER_POLICY = EventFilterPolicy((), (), True, False, False, False)


@dataclass
class Adapters:
    geocoder: DeterministicEventLocationResolver
    router: DeterministicRouteProvider


def calendar(location: str | None) -> HomeAssistantCalendarSource:
    event = SyntheticCalendarEvent(
        start=START,
        end=START + timedelta(hours=1),
        summary="Synthetic appointment",
        location=location,
        uid="synthetic-event",
    )
    return HomeAssistantCalendarSource(
        hass=object(),
        component=SyntheticCalendarComponent(
            {"calendar.synthetic": SyntheticCalendarEntity([event])}
        ),
        config=CalendarSourceConfig(("calendar.synthetic",)),
        classify_online=lambda event: False,
    )


def location(endpoint_id: str, coordinates: Coordinates) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id,
        coordinates,
        LocationProvenance.EVENT,
        None,
        DataQuality.COMPLETE,
    )


class RoutedProfileSourceTests(unittest.TestCase):
    def test_real_pipeline_contract_resolves_routes_persists_and_forecasts(
        self,
    ) -> None:
        text = "Synthetic destination"
        destination = location("event:0", Coordinates(13.0, -33.0))
        origin = zone_anchor_resolver().resolve().start
        route_request = RouteRequest(origin, destination, OPTIONS, START)
        geocoder = DeterministicEventLocationResolver(
            {EventLocationRequest(text): EventLocationSuccess(destination.coordinates)}
        )
        router = DeterministicRouteProvider(
            "synthetic-provider:v1",
            {
                route_request: RouteSuccess(
                    Route(
                        origin,
                        destination,
                        10_000,
                        900,
                        "synthetic-provider",
                        NOW,
                        DataQuality.COMPLETE,
                    )
                )
            },
        )
        builds = 0

        def build() -> Adapters:
            nonlocal builds
            builds += 1
            return Adapters(geocoder, router)

        source = RoutedCalendarProfileSource(
            calendar(text),
            zone_anchor_resolver(),
            FILTER_POLICY,
            OPTIONS,
            FORECAST_POLICY,
            build,
            lambda: "revision:synthetic-1",
            lambda: NOW,
            timedelta(days=7),
        )

        update = asyncio.run(source.read(EMPTY_STATE))

        self.assertEqual(builds, 1)
        self.assertEqual(geocoder.requests, (EventLocationRequest(text),))
        self.assertEqual(router.requests, (route_request,))
        self.assertEqual(len(update.state.revisions), 1)
        self.assertEqual(update.forecasts[0].distance_p50_m, 10_000)
        self.assertEqual(update.forecasts[0].distance_p90_m, 12_500)
        self.assertEqual(update.forecasts[0].quality, DataQuality.PARTIAL)
        self.assertNotIn(text, repr(update))

    def test_geocode_failure_remains_unavailable_and_never_routes(self) -> None:
        text = "Synthetic unresolved destination"
        geocoder = DeterministicEventLocationResolver(
            {
                EventLocationRequest(text): EventLocationFailure(
                    EventLocationFailureCategory.NOT_FOUND, NOW
                )
            }
        )
        router = DeterministicRouteProvider("synthetic-provider:v1", {})
        source = RoutedCalendarProfileSource(
            calendar(text),
            zone_anchor_resolver(),
            FILTER_POLICY,
            OPTIONS,
            FORECAST_POLICY,
            lambda: Adapters(geocoder, router),
            lambda: "revision:synthetic-failure",
            lambda: NOW,
            timedelta(days=7),
        )

        update = asyncio.run(source.read(EMPTY_STATE))

        self.assertEqual(router.requests, ())
        self.assertEqual(update.state.revisions[0].quality, DataQuality.PARTIAL)
        self.assertEqual(
            update.state.revisions[0].legs[0].reason_codes,
            ("destination_geocode_not_found",),
        )
        self.assertIsNone(update.forecasts[0].distance_p90_m)

    def test_included_no_location_event_uses_explicit_end_anchor_fallback(self) -> None:
        anchors = zone_anchor_resolver().resolve()
        fallback = ResolvedLocation(
            "anchor:end-fallback",
            anchors.end.coordinates,
            LocationProvenance.CONFIGURED_FALLBACK,
            None,
            DataQuality.PARTIAL,
        )
        route_request = RouteRequest(anchors.start, fallback, OPTIONS, START)
        geocoder = DeterministicEventLocationResolver({})
        router = DeterministicRouteProvider(
            "synthetic-provider:v1",
            {
                route_request: RouteFailure(
                    RouteFailureCategory.TRANSIENT, "synthetic-provider", NOW
                )
            },
        )
        source = RoutedCalendarProfileSource(
            calendar(None),
            zone_anchor_resolver(),
            FILTER_POLICY,
            OPTIONS,
            FORECAST_POLICY,
            lambda: Adapters(geocoder, router),
            lambda: "revision:synthetic-fallback",
            lambda: NOW,
            timedelta(days=7),
        )

        update = asyncio.run(source.read(EMPTY_STATE))

        self.assertEqual(geocoder.requests, ())
        self.assertEqual(router.requests, (route_request,))
        self.assertEqual(
            update.state.revisions[0].stops[0].destination_reason,
            "configured_fallback",
        )
        self.assertIsNone(update.forecasts[0].distance_p90_m)


if __name__ == "__main__":
    unittest.main()
