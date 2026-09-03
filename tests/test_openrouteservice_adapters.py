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
    RouteFailure,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteResultSource,
    RouteSuccess,
)
from custom_components.mobility_forecast.openrouteservice import (
    ORS_HOSTED_GEOCODING_ENDPOINT,
    ORS_HOSTED_ROUTING_ENDPOINT,
    InMemoryGeocodeCache,
    OpenRouteServiceAdapters,
    OpenRouteServiceGeocodeFailure,
    OpenRouteServiceGeocodeQuery,
    OpenRouteServiceGeocodeResponse,
    OpenRouteServiceGeocodeTransport,
    OpenRouteServiceRouteFailure,
    OpenRouteServiceRouteQuery,
    OpenRouteServiceRouteResponse,
    OpenRouteServiceRouteTransport,
    build_openrouteservice_adapters,
)
from custom_components.mobility_forecast.route_provider_config import (
    CONF_GEOCODE_CACHE_RETENTION_HOURS,
    CONF_GEOCODER_BASE_URL,
    CONF_GEOCODER_PROVIDER,
    CONF_HIGHWAY_POLICY,
    CONF_LOCATION_DATA_CONSENT,
    CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH,
    CONF_MAX_REQUEST_ATTEMPTS,
    CONF_MAX_ROUTE_REQUESTS_PER_REFRESH,
    CONF_REQUEST_TIMEOUT_SECONDS,
    CONF_ROUTE_CACHE_FRESH_HOURS,
    CONF_ROUTE_CACHE_STALE_HOURS,
    CONF_ROUTE_PROVIDER,
    CONF_ROUTE_PROVIDER_API_KEY,
    CONF_ROUTING_BASE_URL,
    CONF_TOLL_POLICY,
    GeocoderKind,
    ProfileRouteConfig,
)

NOW = datetime(2033, 5, 6, 7, 0, tzinfo=UTC)
PRIVATE_TEXT = "Synthetic Private Destination 42"
PRIVACY_KEY = b"synthetic-profile-privacy-key"


def config_data(
    provider: str = "openrouteservice_hosted",
    *,
    maximum_geocodes: int = 3,
    maximum_routes: int = 3,
    maximum_attempts: int = 2,
    timeout_seconds: int = 1,
) -> dict[str, object]:
    data: dict[str, object] = {
        CONF_ROUTE_PROVIDER: provider,
        CONF_LOCATION_DATA_CONSENT: "accepted",
        CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH: maximum_geocodes,
        CONF_MAX_ROUTE_REQUESTS_PER_REFRESH: maximum_routes,
        CONF_MAX_REQUEST_ATTEMPTS: maximum_attempts,
        CONF_REQUEST_TIMEOUT_SECONDS: timeout_seconds,
        CONF_GEOCODE_CACHE_RETENTION_HOURS: 2,
        CONF_ROUTE_CACHE_FRESH_HOURS: 1,
        CONF_ROUTE_CACHE_STALE_HOURS: 3,
        CONF_TOLL_POLICY: "avoid",
        CONF_HIGHWAY_POLICY: "allow",
    }
    if provider == "openrouteservice_self_hosted":
        data.update(
            {
                CONF_ROUTING_BASE_URL: "https://routing.synthetic.invalid/ors",
                CONF_GEOCODER_PROVIDER: "photon",
                CONF_GEOCODER_BASE_URL: "https://geocoder.synthetic.invalid/photon",
            }
        )
    else:
        data[CONF_ROUTE_PROVIDER_API_KEY] = "synthetic-provider-key"
    return data


def location(endpoint_id: str, latitude: float, longitude: float) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id=endpoint_id,
        coordinates=Coordinates(latitude, longitude),
        provenance=LocationProvenance.ZONE,
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


class MutableClock:
    def __init__(self, value: datetime = NOW) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SyntheticGeocodeTransport:
    def __init__(
        self,
        responses: list[
            OpenRouteServiceGeocodeResponse | OpenRouteServiceGeocodeFailure
        ],
    ) -> None:
        self.responses = responses
        self.queries: list[OpenRouteServiceGeocodeQuery] = []

    async def geocode(
        self, query: OpenRouteServiceGeocodeQuery
    ) -> OpenRouteServiceGeocodeResponse | OpenRouteServiceGeocodeFailure:
        self.queries.append(query)
        return self.responses.pop(0)


class SyntheticRouteTransport:
    def __init__(
        self,
        responses: list[OpenRouteServiceRouteResponse | OpenRouteServiceRouteFailure],
    ) -> None:
        self.responses = responses
        self.queries: list[OpenRouteServiceRouteQuery] = []

    async def route(
        self, query: OpenRouteServiceRouteQuery
    ) -> OpenRouteServiceRouteResponse | OpenRouteServiceRouteFailure:
        self.queries.append(query)
        return self.responses.pop(0)


class BlockingGeocodeTransport:
    def __init__(self) -> None:
        self.cancelled = False

    async def geocode(
        self, query: OpenRouteServiceGeocodeQuery
    ) -> OpenRouteServiceGeocodeResponse | OpenRouteServiceGeocodeFailure:
        del query
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


class OpenRouteServiceAdapterTests(unittest.TestCase):
    def build(
        self,
        data: dict[str, object],
        geocode_transport: OpenRouteServiceGeocodeTransport,
        route_transport: OpenRouteServiceRouteTransport,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> OpenRouteServiceAdapters:
        return build_openrouteservice_adapters(
            config=ProfileRouteConfig.from_entry_data(data),
            geocode_transport=geocode_transport,
            route_transport=route_transport,
            geocode_cache=InMemoryGeocodeCache(),
            route_cache=InMemoryRouteCache(),
            privacy_key=PRIVACY_KEY,
            now=clock if clock is not None else MutableClock(),
        )

    def test_hosted_adapters_use_only_fixed_endpoints_and_one_explicit_key(
        self,
    ) -> None:
        geocode_transport = SyntheticGeocodeTransport(
            [OpenRouteServiceGeocodeResponse(Coordinates(51.2, 4.3))]
        )
        route_transport = SyntheticRouteTransport(
            [OpenRouteServiceRouteResponse(12_345, 1_234, NOW)]
        )
        adapters = self.build(config_data(), geocode_transport, route_transport)
        request = RouteRequest(
            origin=location("origin", 51.0, 4.0),
            destination=location("destination", 51.2, 4.3),
            options=RouteOptions(avoid_tolls=True, avoid_highways=False),
            depart_at=NOW,
        )

        geocode_result = asyncio.run(
            adapters.geocoder.resolve(EventLocationRequest(PRIVATE_TEXT))
        )
        route_result = asyncio.run(adapters.router.route(request))

        self.assertEqual(geocode_result, EventLocationSuccess(Coordinates(51.2, 4.3)))
        self.assertIsInstance(route_result, RouteSuccess)
        self.assertEqual(route_result.route.distance_m, 12_345)  # type: ignore[union-attr]
        self.assertEqual(route_result.route.duration_s, 1_234)  # type: ignore[union-attr]
        self.assertEqual(
            geocode_transport.queries,
            [
                OpenRouteServiceGeocodeQuery(
                    endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
                    api_key="synthetic-provider-key",
                    geocoder=GeocoderKind.PELIAS,
                    location_text=PRIVATE_TEXT,
                )
            ],
        )
        self.assertEqual(
            route_transport.queries,
            [
                OpenRouteServiceRouteQuery(
                    endpoint=ORS_HOSTED_ROUTING_ENDPOINT,
                    api_key="synthetic-provider-key",
                    origin=request.origin.coordinates,
                    destination=request.destination.coordinates,
                    avoid_tolls=True,
                    avoid_highways=False,
                    depart_at=NOW,
                )
            ],
        )

    def test_self_hosted_adapters_keep_routing_and_geocoder_separate(self) -> None:
        geocode_transport = SyntheticGeocodeTransport(
            [OpenRouteServiceGeocodeResponse(Coordinates(50.1, 5.2))]
        )
        route_transport = SyntheticRouteTransport(
            [OpenRouteServiceRouteResponse(4_000, 500, NOW)]
        )
        adapters = self.build(
            config_data("openrouteservice_self_hosted"),
            geocode_transport,
            route_transport,
        )
        route_request = RouteRequest(
            origin=location("origin", 50.0, 5.0),
            destination=location("destination", 50.1, 5.2),
            options=RouteOptions(avoid_tolls=False, avoid_highways=True),
            depart_at=None,
        )

        asyncio.run(adapters.geocoder.resolve(EventLocationRequest(PRIVATE_TEXT)))
        asyncio.run(adapters.router.route(route_request))

        self.assertEqual(
            geocode_transport.queries[0].endpoint,
            "https://geocoder.synthetic.invalid/photon",
        )
        self.assertEqual(geocode_transport.queries[0].geocoder, GeocoderKind.PHOTON)
        self.assertIsNone(geocode_transport.queries[0].api_key)
        self.assertEqual(
            route_transport.queries[0].endpoint,
            "https://routing.synthetic.invalid/ors",
        )
        self.assertIsNone(route_transport.queries[0].api_key)
        self.assertNotEqual(
            adapters.geocoder.cache_namespace, adapters.router.cache_namespace
        )

    def test_factory_rejects_non_ors_provider_without_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "OpenRouteService"):
            self.build(
                config_data("geoapify"),
                SyntheticGeocodeTransport([]),
                SyntheticRouteTransport([]),
            )

    def test_retryable_failures_retry_but_nonretryable_failures_do_not(self) -> None:
        retrying_transport = SyntheticGeocodeTransport(
            [
                OpenRouteServiceGeocodeFailure(
                    EventLocationFailureCategory.TRANSIENT, NOW
                ),
                OpenRouteServiceGeocodeResponse(Coordinates(51.2, 4.3)),
            ]
        )
        adapters = self.build(
            config_data(maximum_attempts=2),
            retrying_transport,
            SyntheticRouteTransport([]),
        )

        result = asyncio.run(
            adapters.geocoder.resolve(EventLocationRequest(PRIVATE_TEXT))
        )

        self.assertIsInstance(result, EventLocationSuccess)
        self.assertEqual(len(retrying_transport.queries), 2)
        self.assertEqual(adapters.budget.geocode_requests, 2)

        nonretrying_transport = SyntheticRouteTransport(
            [OpenRouteServiceRouteFailure(RouteFailureCategory.INVALID_INPUT, NOW)]
        )
        adapters = self.build(
            config_data(maximum_attempts=2),
            SyntheticGeocodeTransport([]),
            nonretrying_transport,
        )
        route_request = RouteRequest(
            origin=location("origin", 51.0, 4.0),
            destination=location("destination", 51.1, 4.2),
            options=RouteOptions(False, False),
            depart_at=None,
        )

        route_result = asyncio.run(adapters.router.route(route_request))

        self.assertEqual(
            route_result,
            RouteFailure(
                RouteFailureCategory.INVALID_INPUT,
                "openrouteservice_hosted",
                NOW,
            ),
        )
        self.assertEqual(len(nonretrying_transport.queries), 1)

    def test_hard_refresh_budget_fails_closed_before_extra_transport_call(self) -> None:
        transport = SyntheticGeocodeTransport(
            [
                OpenRouteServiceGeocodeFailure(
                    EventLocationFailureCategory.TRANSIENT, NOW
                )
            ]
        )
        adapters = self.build(
            config_data(maximum_geocodes=1, maximum_attempts=2),
            transport,
            SyntheticRouteTransport([]),
        )

        result = asyncio.run(
            adapters.geocoder.resolve(EventLocationRequest(PRIVATE_TEXT))
        )

        self.assertEqual(
            result,
            EventLocationFailure(EventLocationFailureCategory.QUOTA_EXCEEDED, NOW),
        )
        self.assertEqual(len(transport.queries), 1)
        self.assertEqual(adapters.budget.geocode_requests, 1)

    def test_timeout_is_bounded_cancelled_and_mapped_to_typed_failure(self) -> None:
        transport = BlockingGeocodeTransport()
        data = config_data(maximum_attempts=1, timeout_seconds=1)
        adapters = self.build(
            data,
            transport,
            SyntheticRouteTransport([]),
        )

        result = asyncio.run(
            adapters.geocoder.resolve(EventLocationRequest(PRIVATE_TEXT))
        )

        self.assertEqual(
            result,
            EventLocationFailure(EventLocationFailureCategory.TRANSIENT, NOW),
        )
        self.assertTrue(transport.cancelled)
        self.assertEqual(adapters.budget.geocode_requests, 1)

    def test_geocode_cache_is_opaque_and_evicts_expired_entries(self) -> None:
        clock = MutableClock()
        transport = SyntheticGeocodeTransport(
            [
                OpenRouteServiceGeocodeResponse(Coordinates(51.2, 4.3)),
                OpenRouteServiceGeocodeResponse(Coordinates(51.3, 4.4)),
            ]
        )
        adapters = self.build(
            config_data(), transport, SyntheticRouteTransport([]), clock=clock
        )
        request = EventLocationRequest(PRIVATE_TEXT)

        first = asyncio.run(adapters.geocoder.resolve(request))
        cached = asyncio.run(adapters.geocoder.resolve(request))
        clock.value = NOW + timedelta(hours=2, microseconds=1)
        refreshed = asyncio.run(adapters.geocoder.resolve(request))

        self.assertEqual(first, EventLocationSuccess(Coordinates(51.2, 4.3)))
        self.assertEqual(cached, first)
        self.assertEqual(refreshed, EventLocationSuccess(Coordinates(51.3, 4.4)))
        self.assertEqual(len(transport.queries), 2)
        self.assertEqual(adapters.budget.geocode_requests, 2)

    def test_route_cache_uses_configured_fresh_and_stale_policy(self) -> None:
        clock = MutableClock()
        transport = SyntheticRouteTransport(
            [
                OpenRouteServiceRouteResponse(10_000, 1_000, NOW),
                OpenRouteServiceRouteFailure(RouteFailureCategory.TRANSIENT, NOW),
                OpenRouteServiceRouteFailure(RouteFailureCategory.TRANSIENT, NOW),
            ]
        )
        adapters = self.build(
            config_data(maximum_attempts=1),
            SyntheticGeocodeTransport([]),
            transport,
            clock=clock,
        )
        request = RouteRequest(
            origin=location("origin", 51.0, 4.0),
            destination=location("destination", 51.1, 4.2),
            options=RouteOptions(False, False),
            depart_at=None,
        )

        first = asyncio.run(adapters.router.route(request))
        cached = asyncio.run(adapters.router.route(request))
        clock.value = NOW + timedelta(hours=1, microseconds=1)
        stale = asyncio.run(adapters.router.route(request))
        clock.value = NOW + timedelta(hours=3, microseconds=1)
        expired = asyncio.run(adapters.router.route(request))

        self.assertIsInstance(first, RouteSuccess)
        self.assertEqual(cached.source, RouteResultSource.CACHE)  # type: ignore[union-attr]
        self.assertEqual(stale.source, RouteResultSource.STALE_CACHE)  # type: ignore[union-attr]
        self.assertEqual(stale.route.quality, DataQuality.STALE)  # type: ignore[union-attr]
        self.assertEqual(  # type: ignore[union-attr]
            stale.refresh_failure, RouteFailureCategory.TRANSIENT
        )
        self.assertIsInstance(expired, RouteFailure)
        self.assertEqual(len(transport.queries), 3)
        self.assertEqual(adapters.budget.route_requests, 3)

    def test_query_and_adapter_representations_hide_private_values(self) -> None:
        geocode_query = OpenRouteServiceGeocodeQuery(
            endpoint="https://private.synthetic.invalid/geocode",
            api_key="synthetic-secret",
            geocoder=GeocoderKind.NOMINATIM,
            location_text=PRIVATE_TEXT,
        )
        route_query = OpenRouteServiceRouteQuery(
            endpoint="https://private.synthetic.invalid/route",
            api_key="synthetic-secret",
            origin=Coordinates(51.123, 4.456),
            destination=Coordinates(51.234, 4.567),
            avoid_tolls=False,
            avoid_highways=False,
            depart_at=NOW,
        )
        adapters = self.build(
            config_data("openrouteservice_self_hosted"),
            SyntheticGeocodeTransport([]),
            SyntheticRouteTransport([]),
        )

        rendered = repr((geocode_query, route_query, adapters))

        for private_value in (
            PRIVATE_TEXT,
            "synthetic-secret",
            "private.synthetic.invalid",
            "geocoder.synthetic.invalid",
            "routing.synthetic.invalid",
            "51.123",
            "4.567",
        ):
            self.assertNotIn(private_value, rendered)


if __name__ == "__main__":
    unittest.main()
