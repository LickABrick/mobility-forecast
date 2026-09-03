from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime

from custom_components.mobility_forecast.domain import (
    Coordinates,
    EventLocationFailureCategory,
    RouteFailureCategory,
)
from custom_components.mobility_forecast.geoapify import (
    GeoapifyGeocodeFailure,
    GeoapifyGeocodeQuery,
    GeoapifyGeocodeResponse,
    GeoapifyRouteFailure,
    GeoapifyRouteQuery,
    GeoapifyRouteResponse,
)
from custom_components.mobility_forecast.geoapify_http import (
    GeoapifyHttpGeocodeTransport,
    GeoapifyHttpRouteTransport,
)
from custom_components.mobility_forecast.openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResponse,
)
from custom_components.mobility_forecast.route_provider_config import (
    GEOAPIFY_GEOCODING_ENDPOINT,
    GEOAPIFY_ROUTING_ENDPOINT,
)

NOW = datetime(2036, 7, 8, 9, 10, 11, tzinfo=UTC)
PRIVATE_TEXT = "Synthetic Private Destination 84"
PRIVATE_KEY = "synthetic-geoapify-key"
ORIGIN = Coordinates(51.0, 4.0)
DESTINATION = Coordinates(51.2, 4.3)


class SyntheticHttpSender:
    def __init__(
        self, results: list[InjectedHttpResponse | InjectedHttpFailure]
    ) -> None:
        self.results = results
        self.requests: list[InjectedHttpRequest] = []

    async def send(
        self, request: InjectedHttpRequest
    ) -> InjectedHttpResponse | InjectedHttpFailure:
        self.requests.append(request)
        return self.results.pop(0)


class GeoapifyHttpTransportTests(unittest.TestCase):
    def test_geocode_shapes_fixed_request_and_decodes_first_geojson_point(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [4.3, 51.2],
                                },
                                "properties": {"formatted": "private echo"},
                            }
                        ],
                    },
                )
            ]
        )
        transport = GeoapifyHttpGeocodeTransport(sender=sender, now=lambda: NOW)

        result = asyncio.run(
            transport.geocode(GeoapifyGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT))
        )

        self.assertEqual(result, GeoapifyGeocodeResponse(Coordinates(51.2, 4.3)))
        self.assertEqual(
            sender.requests,
            [
                InjectedHttpRequest(
                    method="GET",
                    url=GEOAPIFY_GEOCODING_ENDPOINT,
                    headers=(("Accept", "application/json"),),
                    query=(
                        ("text", PRIVATE_TEXT),
                        ("limit", "1"),
                        ("format", "geojson"),
                        ("apiKey", PRIVATE_KEY),
                    ),
                    json_body=None,
                )
            ],
        )
        self.assertNotIn(PRIVATE_KEY, repr(sender.requests[0]))
        self.assertNotIn(PRIVATE_TEXT, repr(sender.requests[0]))

    def test_route_shapes_fixed_get_with_explicit_binary_avoidance(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "properties": {
                                    "distance": 12_345.6,
                                    "time": 1_234.2,
                                },
                                "geometry": {"private": "echo"},
                            }
                        ],
                    },
                )
            ]
        )
        transport = GeoapifyHttpRouteTransport(
            sender=sender, api_key=PRIVATE_KEY, now=lambda: NOW
        )

        result = asyncio.run(
            transport.route(
                GeoapifyRouteQuery(
                    ORIGIN,
                    DESTINATION,
                    avoid_tolls=True,
                    avoid_highways=True,
                    depart_at=NOW,
                )
            )
        )

        self.assertEqual(result, GeoapifyRouteResponse(12_346, 1_235, NOW))
        self.assertEqual(
            sender.requests,
            [
                InjectedHttpRequest(
                    method="GET",
                    url=GEOAPIFY_ROUTING_ENDPOINT,
                    headers=(("Accept", "application/json"),),
                    query=(
                        ("waypoints", "51.0,4.0|51.2,4.3"),
                        ("mode", "drive"),
                        ("units", "metric"),
                        ("avoid", "tolls|highways"),
                        ("format", "geojson"),
                        ("apiKey", PRIVATE_KEY),
                    ),
                    json_body=None,
                )
            ],
        )
        self.assertNotIn(PRIVATE_KEY, repr(sender.requests[0]))
        self.assertNotIn("51.0", repr(sender.requests[0]))

    def test_route_omits_avoid_parameter_when_both_choices_allow(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {"features": [{"properties": {"distance": 4_000, "time": 500}}]},
                )
            ]
        )
        transport = GeoapifyHttpRouteTransport(
            sender=sender, api_key=PRIVATE_KEY, now=lambda: NOW
        )

        result = asyncio.run(
            transport.route(GeoapifyRouteQuery(ORIGIN, DESTINATION, False, False, None))
        )

        self.assertEqual(result, GeoapifyRouteResponse(4_000, 500, NOW))
        self.assertNotIn("avoid", dict(sender.requests[0].query))

    def test_http_and_sender_failures_map_to_stable_categories(self) -> None:
        geocode_cases = (
            (InjectedHttpResponse(400, {}), EventLocationFailureCategory.INVALID_INPUT),
            (InjectedHttpResponse(404, {}), EventLocationFailureCategory.NOT_FOUND),
            (InjectedHttpResponse(429, {}), EventLocationFailureCategory.RATE_LIMITED),
            (
                InjectedHttpResponse(401, {}),
                EventLocationFailureCategory.QUOTA_EXCEEDED,
            ),
            (InjectedHttpResponse(503, {}), EventLocationFailureCategory.TRANSIENT),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE),
                EventLocationFailureCategory.UNAVAILABLE,
            ),
        )
        for sender_result, expected in geocode_cases:
            with self.subTest(role="geocode", expected=expected):
                result = asyncio.run(
                    GeoapifyHttpGeocodeTransport(
                        sender=SyntheticHttpSender([sender_result]), now=lambda: NOW
                    ).geocode(GeoapifyGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT))
                )
                self.assertEqual(result, GeoapifyGeocodeFailure(expected, NOW))

        route_cases = (
            (InjectedHttpResponse(400, {}), RouteFailureCategory.INVALID_INPUT),
            (InjectedHttpResponse(429, {}), RouteFailureCategory.RATE_LIMITED),
            (InjectedHttpResponse(403, {}), RouteFailureCategory.QUOTA_EXCEEDED),
            (InjectedHttpResponse(503, {}), RouteFailureCategory.TRANSIENT),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.TRANSIENT),
                RouteFailureCategory.TRANSIENT,
            ),
        )
        for sender_result, expected in route_cases:
            with self.subTest(role="route", expected=expected):
                result = asyncio.run(
                    GeoapifyHttpRouteTransport(
                        sender=SyntheticHttpSender([sender_result]),
                        api_key=PRIVATE_KEY,
                        now=lambda: NOW,
                    ).route(GeoapifyRouteQuery(ORIGIN, DESTINATION, False, False, None))
                )
                self.assertEqual(result, GeoapifyRouteFailure(expected, NOW))

    def test_empty_and_malformed_successes_fail_closed(self) -> None:
        geocode_bodies = (
            {"features": []},
            {},
            {"features": [{"geometry": {"type": "LineString", "coordinates": []}}]},
            {
                "features": [
                    {"geometry": {"type": "Point", "coordinates": [181.0, 51.2]}}
                ]
            },
        )
        for body in geocode_bodies:
            with self.subTest(role="geocode", body=body):
                result = asyncio.run(
                    GeoapifyHttpGeocodeTransport(
                        sender=SyntheticHttpSender([InjectedHttpResponse(200, body)]),
                        now=lambda: NOW,
                    ).geocode(GeoapifyGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT))
                )
                expected = (
                    EventLocationFailureCategory.NOT_FOUND
                    if body == {"features": []}
                    else EventLocationFailureCategory.UNAVAILABLE
                )
                self.assertEqual(result, GeoapifyGeocodeFailure(expected, NOW))

        route_bodies = (
            {"features": []},
            {},
            {"features": [{"properties": {"distance": 0, "time": 500}}]},
            {"features": [{"properties": {"distance": 4_000, "time": "bad"}}]},
        )
        for body in route_bodies:
            with self.subTest(role="route", body=body):
                result = asyncio.run(
                    GeoapifyHttpRouteTransport(
                        sender=SyntheticHttpSender([InjectedHttpResponse(200, body)]),
                        api_key=PRIVATE_KEY,
                        now=lambda: NOW,
                    ).route(GeoapifyRouteQuery(ORIGIN, DESTINATION, False, False, None))
                )
                self.assertEqual(
                    result,
                    GeoapifyRouteFailure(RouteFailureCategory.UNAVAILABLE, NOW),
                )


if __name__ == "__main__":
    unittest.main()
