from __future__ import annotations

import asyncio
import unittest
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    EventLocationFailure,
    EventLocationFailureCategory,
    EventLocationRequest,
    EventLocationSuccess,
    InMemoryRouteCache,
    LocationProvenance,
    ResolvedLocation,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteResultSource,
    RouteSuccess,
)
from custom_components.mobility_forecast.geoapify import (
    GEOAPIFY_GEOCODING_CACHE_NAMESPACE,
    GEOAPIFY_ROUTES_CACHE_NAMESPACE,
    GeoapifyAdapters,
    GeoapifyGeocodeFailure,
    GeoapifyGeocodeQuery,
    GeoapifyGeocodeResponse,
    GeoapifyGeocodeTransport,
    GeoapifyRouteFailure,
    GeoapifyRouteQuery,
    GeoapifyRouteResponse,
    GeoapifyRouteTransport,
    build_geoapify_adapters,
)
from custom_components.mobility_forecast.openrouteservice import InMemoryGeocodeCache
from custom_components.mobility_forecast.route_provider_config import ProfileRouteConfig

NOW = datetime(2036, 7, 8, 9, 0, tzinfo=UTC)
PRIVATE_TEXT = "Synthetic Private Destination 84"
PRIVACY_KEY = b"synthetic-profile-privacy-key"


def config_data(
    provider: str = "geoapify",
    *,
    maximum_geocodes: int = 3,
    maximum_routes: int = 3,
    maximum_attempts: int = 2,
) -> dict[str, object]:
    return {
        "route_provider": provider,
        "route_provider_api_key": "synthetic-geoapify-key",
        "location_data_consent": "accepted",
        "max_geocode_requests_per_refresh": maximum_geocodes,
        "max_route_requests_per_refresh": maximum_routes,
        "max_request_attempts": maximum_attempts,
        "request_timeout_seconds": 1,
        "geocode_cache_retention_hours": 2,
        "route_cache_fresh_hours": 1,
        "route_cache_stale_hours": 3,
        "toll_policy": "avoid",
        "highway_policy": "allow",
    }


def location(endpoint_id: str, latitude: float, longitude: float) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id,
        Coordinates(latitude, longitude),
        LocationProvenance.ZONE,
        NOW,
        DataQuality.COMPLETE,
    )


class MutableClock:
    def __init__(self, value: datetime = NOW) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SyntheticGeocodeTransport:
    def __init__(
        self, responses: list[GeoapifyGeocodeResponse | GeoapifyGeocodeFailure]
    ) -> None:
        self.responses = responses
        self.queries: list[GeoapifyGeocodeQuery] = []

    async def geocode(
        self, query: GeoapifyGeocodeQuery
    ) -> GeoapifyGeocodeResponse | GeoapifyGeocodeFailure:
        self.queries.append(query)
        return self.responses.pop(0)


class SyntheticRouteTransport:
    def __init__(
        self, responses: list[GeoapifyRouteResponse | GeoapifyRouteFailure]
    ) -> None:
        self.responses = responses
        self.queries: list[GeoapifyRouteQuery] = []

    async def route(
        self, query: GeoapifyRouteQuery
    ) -> GeoapifyRouteResponse | GeoapifyRouteFailure:
        self.queries.append(query)
        return self.responses.pop(0)


class GeoapifyAdapterTests(unittest.TestCase):
    def build(
        self,
        geocode_transport: GeoapifyGeocodeTransport,
        route_transport: GeoapifyRouteTransport,
        *,
        data: dict[str, object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> GeoapifyAdapters:
        return build_geoapify_adapters(
            config=ProfileRouteConfig.from_entry_data(
                config_data() if data is None else data
            ),
            geocode_transport=geocode_transport,
            route_transport=route_transport,
            geocode_cache=InMemoryGeocodeCache(),
            route_cache=InMemoryRouteCache(),
            privacy_key=PRIVACY_KEY,
            now=MutableClock() if clock is None else clock,
        )

    def test_maps_synthetic_successes_through_provider_neutral_boundaries(self) -> None:
        geocode_transport = SyntheticGeocodeTransport(
            [GeoapifyGeocodeResponse(Coordinates(51.2, 4.3))]
        )
        route_transport = SyntheticRouteTransport(
            [GeoapifyRouteResponse(12_345, 1_234, NOW)]
        )
        adapters = self.build(geocode_transport, route_transport)
        origin = location("origin", 51.0, 4.0)
        destination = location("destination", 51.2, 4.3)
        route_request = RouteRequest(
            origin,
            destination,
            RouteOptions(avoid_tolls=True, avoid_highways=False),
            NOW,
        )

        geocode_result = asyncio.run(
            adapters.geocoder.resolve(EventLocationRequest(PRIVATE_TEXT))
        )
        route_result = asyncio.run(adapters.router.route(route_request))

        self.assertEqual(geocode_result, EventLocationSuccess(destination.coordinates))
        self.assertIsInstance(route_result, RouteSuccess)
        self.assertEqual(route_result.route.distance_m, 12_345)  # type: ignore[union-attr]
        self.assertEqual(route_result.route.provider, "geoapify")  # type: ignore[union-attr]
        self.assertEqual(
            geocode_transport.queries,
            [GeoapifyGeocodeQuery("synthetic-geoapify-key", PRIVATE_TEXT)],
        )
        self.assertEqual(
            route_transport.queries,
            [
                GeoapifyRouteQuery(
                    origin.coordinates,
                    destination.coordinates,
                    avoid_tolls=True,
                    avoid_highways=False,
                    depart_at=NOW,
                )
            ],
        )
        self.assertEqual(
            adapters.geocoder.cache_namespace,
            GEOAPIFY_GEOCODING_CACHE_NAMESPACE,
        )
        self.assertEqual(
            adapters.router.cache_namespace, GEOAPIFY_ROUTES_CACHE_NAMESPACE
        )

    def test_retry_budget_and_geocode_cache_are_enforced(self) -> None:
        transport = SyntheticGeocodeTransport(
            [
                GeoapifyGeocodeFailure(EventLocationFailureCategory.TRANSIENT, NOW),
                GeoapifyGeocodeResponse(Coordinates(51.2, 4.3)),
            ]
        )
        adapters = self.build(transport, SyntheticRouteTransport([]))
        request = EventLocationRequest(PRIVATE_TEXT)

        first = asyncio.run(adapters.geocoder.resolve(request))
        cached = asyncio.run(adapters.geocoder.resolve(request))

        self.assertEqual(first, EventLocationSuccess(Coordinates(51.2, 4.3)))
        self.assertEqual(cached, first)
        self.assertEqual(len(transport.queries), 2)
        self.assertEqual(adapters.budget.geocode_requests, 2)

        exhausted_transport = SyntheticGeocodeTransport(
            [GeoapifyGeocodeFailure(EventLocationFailureCategory.TRANSIENT, NOW)]
        )
        exhausted = self.build(
            exhausted_transport,
            SyntheticRouteTransport([]),
            data=config_data(maximum_geocodes=1, maximum_attempts=2),
        )
        result = asyncio.run(exhausted.geocoder.resolve(request))
        self.assertEqual(
            result,
            EventLocationFailure(EventLocationFailureCategory.QUOTA_EXCEEDED, NOW),
        )
        self.assertEqual(len(exhausted_transport.queries), 1)

    def test_route_cache_preserves_explicit_stale_failure_semantics(self) -> None:
        clock = MutableClock()
        transport = SyntheticRouteTransport(
            [
                GeoapifyRouteResponse(10_000, 900, NOW),
                GeoapifyRouteFailure(RouteFailureCategory.TRANSIENT, NOW),
            ]
        )
        adapters = self.build(
            SyntheticGeocodeTransport([]),
            transport,
            data=config_data(maximum_attempts=1),
            clock=clock,
        )
        request = RouteRequest(
            location("origin", 51.0, 4.0),
            location("destination", 51.2, 4.3),
            RouteOptions(False, False),
            None,
        )

        first = asyncio.run(adapters.router.route(request))
        cached = asyncio.run(adapters.router.route(request))
        clock.value = NOW + timedelta(hours=1, microseconds=1)
        stale = asyncio.run(adapters.router.route(request))

        self.assertIsInstance(first, RouteSuccess)
        self.assertEqual(cached.source, RouteResultSource.CACHE)  # type: ignore[union-attr]
        self.assertEqual(stale.source, RouteResultSource.STALE_CACHE)  # type: ignore[union-attr]
        self.assertEqual(stale.route.quality, DataQuality.STALE)  # type: ignore[union-attr]
        self.assertEqual(stale.refresh_failure, RouteFailureCategory.TRANSIENT)  # type: ignore[union-attr]
        self.assertEqual(len(transport.queries), 2)

    def test_factory_rejects_other_provider_without_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "Geoapify"):
            self.build(
                SyntheticGeocodeTransport([]),
                SyntheticRouteTransport([]),
                data={**config_data(), "route_provider": "google"},
            )

    def test_private_query_and_adapter_values_are_absent_from_representations(
        self,
    ) -> None:
        adapters = self.build(
            SyntheticGeocodeTransport([]), SyntheticRouteTransport([])
        )
        rendered = repr(
            (
                GeoapifyGeocodeQuery("synthetic-secret", PRIVATE_TEXT),
                GeoapifyRouteQuery(
                    Coordinates(51.123, 4.456),
                    Coordinates(51.234, 4.567),
                    False,
                    True,
                    NOW,
                ),
                adapters,
            )
        )

        for private_value in (
            PRIVATE_TEXT,
            "synthetic-secret",
            "51.123",
            "4.567",
        ):
            self.assertNotIn(private_value, rendered)


if __name__ == "__main__":
    unittest.main()
