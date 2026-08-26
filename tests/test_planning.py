from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    DeterministicRouteProvider,
    ItineraryCandidate,
    LocationProvenance,
    PlanRevision,
    ResolvedLocation,
    Route,
    RouteFailure,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteSuccess,
    SourceEvent,
    append_plan_revision,
    assemble_plan_revision,
)

NOW = datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
SERVICE_DATE = date(2026, 1, 15)
OPTIONS = RouteOptions(avoid_tolls=False, avoid_highways=False)


def location(endpoint_id: str, offset: float = 0.0) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id=endpoint_id,
        coordinates=Coordinates(40.0 + offset, -10.0 - offset),
        provenance=LocationProvenance.ZONE,
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


def event(
    source_id: str,
    event_id: str,
    starts_at: datetime,
    *,
    ends_after: timedelta = timedelta(hours=1),
) -> SourceEvent:
    return SourceEvent(
        source_id=source_id,
        event_id=event_id,
        starts_at=starts_at,
        ends_at=starts_at + ends_after,
        all_day=False,
        is_online=False,
        summary="synthetic appointment",
        location_text="synthetic place",
    )


def candidate(
    source_id: str,
    event_id: str,
    starts_at: datetime,
    destination: ResolvedLocation | None,
    *,
    dedupe_key: str | None = None,
) -> ItineraryCandidate:
    return ItineraryCandidate(
        event=event(source_id, event_id, starts_at),
        deduplication_key=dedupe_key or f"key:{event_id}",
        destination=destination,
        destination_reason=(
            "primary_missing" if destination is None else "primary_accepted"
        ),
    )


def route(request: RouteRequest, distance_m: int = 10_000) -> Route:
    return Route(
        origin=request.origin,
        destination=request.destination,
        distance_m=distance_m,
        duration_s=900,
        provider="deterministic-fake",
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


class ItineraryAssemblyTests(unittest.IsolatedAsyncioTestCase):
    async def test_orders_stops_and_chains_destinations_to_origins(self) -> None:
        home = location("synthetic:home")
        early = location("synthetic:early", 1.0)
        late = location("synthetic:late", 2.0)
        early_event = candidate(
            "calendar:b", "event:early", NOW + timedelta(hours=2), early
        )
        late_event = candidate(
            "calendar:a", "event:late", NOW + timedelta(hours=5), late
        )
        first_request = RouteRequest(home, early, OPTIONS, early_event.event.starts_at)
        second_request = RouteRequest(early, late, OPTIONS, late_event.event.starts_at)
        provider = DeterministicRouteProvider(
            "deterministic-fake:v1",
            {
                first_request: RouteSuccess(route(first_request)),
                second_request: RouteSuccess(route(second_request)),
            },
        )

        revision = await assemble_plan_revision(
            revision_id="revision:1",
            service_date=SERVICE_DATE,
            created_at=NOW,
            source_observed_at=NOW,
            candidates=(late_event, early_event),
            initial_origin=home,
            route_options=OPTIONS,
            route_provider=provider,
        )

        self.assertEqual(
            tuple(stop.event_id for stop in revision.stops),
            ("event:early", "event:late"),
        )
        self.assertEqual(provider.requests, (first_request, second_request))
        self.assertEqual(revision.legs[1].origin, early)
        self.assertEqual(revision.quality, DataQuality.COMPLETE)

    async def test_deduplicates_cross_calendar_events_deterministically(self) -> None:
        home = location("synthetic:home")
        destination = location("synthetic:destination", 1.0)
        starts_at = NOW + timedelta(hours=2)
        from_b = candidate(
            "calendar:b", "event:b", starts_at, destination, dedupe_key="shared"
        )
        from_a = candidate(
            "calendar:a", "event:a", starts_at, destination, dedupe_key="shared"
        )
        request = RouteRequest(home, destination, OPTIONS, starts_at)
        provider = DeterministicRouteProvider(
            "deterministic-fake:v1", {request: RouteSuccess(route(request))}
        )

        revision = await assemble_plan_revision(
            revision_id="revision:dedupe",
            service_date=SERVICE_DATE,
            created_at=NOW,
            source_observed_at=NOW,
            candidates=(from_b, from_a),
            initial_origin=home,
            route_options=OPTIONS,
            route_provider=provider,
        )

        self.assertEqual(len(revision.stops), 1)
        self.assertEqual(revision.stops[0].event_id, "event:a")
        self.assertEqual(
            revision.stops[0].source_references,
            (("calendar:a", "event:a"), ("calendar:b", "event:b")),
        )
        self.assertEqual(provider.requests, (request,))

    async def test_rejects_conflicting_candidates_with_same_key(self) -> None:
        destination = location("synthetic:destination", 1.0)
        candidates = (
            candidate(
                "calendar:a",
                "event:a",
                NOW + timedelta(hours=2),
                destination,
                dedupe_key="shared",
            ),
            candidate(
                "calendar:b",
                "event:b",
                NOW + timedelta(hours=3),
                destination,
                dedupe_key="shared",
            ),
        )

        with self.assertRaises(ValueError):
            await assemble_plan_revision(
                revision_id="revision:conflict",
                service_date=SERVICE_DATE,
                created_at=NOW,
                source_observed_at=NOW,
                candidates=candidates,
                initial_origin=location("synthetic:home"),
                route_options=OPTIONS,
                route_provider=DeterministicRouteProvider("fake:v1", {}),
            )

    async def test_route_failure_is_partial_and_chaining_continues(self) -> None:
        home = location("synthetic:home")
        first = location("synthetic:first", 1.0)
        second = location("synthetic:second", 2.0)
        one = candidate("calendar:a", "event:one", NOW + timedelta(hours=2), first)
        two = candidate("calendar:a", "event:two", NOW + timedelta(hours=4), second)
        first_request = RouteRequest(home, first, OPTIONS, one.event.starts_at)
        second_request = RouteRequest(first, second, OPTIONS, two.event.starts_at)
        failure = RouteFailure(RouteFailureCategory.TRANSIENT, "fake", NOW)
        provider = DeterministicRouteProvider(
            "fake:v1",
            {
                first_request: failure,
                second_request: RouteSuccess(route(second_request)),
            },
        )

        revision = await assemble_plan_revision(
            revision_id="revision:partial",
            service_date=SERVICE_DATE,
            created_at=NOW,
            source_observed_at=NOW,
            candidates=(one, two),
            initial_origin=home,
            route_options=OPTIONS,
            route_provider=provider,
        )

        self.assertIsNone(revision.legs[0].route)
        self.assertEqual(revision.legs[0].reason_codes, ("route_transient",))
        self.assertEqual(revision.legs[0].quality, DataQuality.PARTIAL)
        self.assertEqual(revision.legs[1].quality, DataQuality.COMPLETE)
        self.assertEqual(revision.quality, DataQuality.PARTIAL)
        self.assertEqual(provider.requests, (first_request, second_request))

    async def test_unknown_destination_breaks_chain_without_a_route_call(self) -> None:
        home = location("synthetic:home")
        later = location("synthetic:later", 2.0)
        missing = candidate(
            "calendar:a", "event:missing", NOW + timedelta(hours=2), None
        )
        known = candidate("calendar:a", "event:known", NOW + timedelta(hours=4), later)
        provider = DeterministicRouteProvider("fake:v1", {})

        revision = await assemble_plan_revision(
            revision_id="revision:broken-chain",
            service_date=SERVICE_DATE,
            created_at=NOW,
            source_observed_at=NOW,
            candidates=(missing, known),
            initial_origin=home,
            route_options=OPTIONS,
            route_provider=provider,
        )

        self.assertEqual(provider.requests, ())
        self.assertEqual(revision.legs[0].quality, DataQuality.UNAVAILABLE)
        self.assertEqual(
            revision.legs[0].reason_codes,
            ("destination_primary_missing",),
        )
        self.assertEqual(revision.legs[1].reason_codes, ("origin_unavailable",))
        self.assertEqual(revision.quality, DataQuality.PARTIAL)


class PlanRevisionTests(unittest.TestCase):
    def revision(self, revision_id: str, created_at: datetime) -> PlanRevision:
        return PlanRevision(
            revision_id=revision_id,
            service_date=SERVICE_DATE,
            created_at=created_at,
            source_observed_at=created_at,
            stops=(),
            legs=(),
            quality=DataQuality.UNAVAILABLE,
            reason_codes=("no_stops",),
        )

    def test_append_preserves_history_and_rejects_invalid_append(self) -> None:
        first = self.revision("revision:1", NOW)
        history = append_plan_revision((), first)
        second = self.revision("revision:2", NOW + timedelta(minutes=5))
        updated = append_plan_revision(history, second)

        self.assertEqual(history, (first,))
        self.assertEqual(updated, (first, second))
        self.assertIs(updated[0], first)
        with self.assertRaises(ValueError):
            append_plan_revision(
                updated,
                self.revision("revision:1", NOW + timedelta(minutes=10)),
            )
        with self.assertRaises(ValueError):
            append_plan_revision(
                updated,
                self.revision("revision:3", NOW - timedelta(seconds=1)),
            )

    def test_revision_is_immutable_and_private_values_are_hidden(self) -> None:
        revision = self.revision("revision:private", NOW)
        with self.assertRaises(FrozenInstanceError):
            revision.quality = DataQuality.COMPLETE  # type: ignore[misc]

        private_candidate = candidate(
            "calendar:private",
            "event:private",
            NOW + timedelta(hours=2),
            location("private:endpoint", 1.0),
        )
        self.assertNotIn("calendar:private", repr(private_candidate))
        self.assertNotIn("event:private", repr(private_candidate))
        self.assertNotIn("private:endpoint", repr(private_candidate))


if __name__ == "__main__":
    unittest.main()
