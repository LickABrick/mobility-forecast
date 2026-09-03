from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime

from custom_components.mobility_forecast.domain import (
    Coordinates,
    EventLocationFailureCategory,
    RouteFailureCategory,
)
from custom_components.mobility_forecast.google_routes import (
    GoogleGeocodeFailure,
    GoogleGeocodeQuery,
    GoogleGeocodeResponse,
    GoogleRoutesFailure,
    GoogleRoutesQuery,
    GoogleRoutesResponse,
)
from custom_components.mobility_forecast.google_routes_http import (
    GoogleHttpGeocodeTransport,
    GoogleHttpRouteTransport,
)
from custom_components.mobility_forecast.openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResponse,
)
from custom_components.mobility_forecast.route_provider_config import (
    GOOGLE_GEOCODING_ENDPOINT,
    GOOGLE_ROUTING_ENDPOINT,
)

NOW = datetime(2033, 5, 6, 7, 8, 9, tzinfo=UTC)
PRIVATE_TEXT = "Synthetic Private Destination 42"
PRIVATE_KEY = "synthetic-provider-key"
ORIGIN = Coordinates(51.0, 4.0)
DESTINATION = Coordinates(51.2, 4.3)


class SyntheticHttpSender:
    def __init__(
        self,
        results: list[InjectedHttpResponse | InjectedHttpFailure],
    ) -> None:
        self.results = results
        self.requests: list[InjectedHttpRequest] = []

    async def send(
        self, request: InjectedHttpRequest
    ) -> InjectedHttpResponse | InjectedHttpFailure:
        self.requests.append(request)
        return self.results.pop(0)


class GoogleGeocodeHttpTransportTests(unittest.TestCase):
    def test_geocode_shapes_documented_v3_request_and_response(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "status": "OK",
                        "results": [
                            {
                                "geometry": {"location": {"lat": 51.2, "lng": 4.3}},
                                "formatted_address": "private echo",
                            }
                        ],
                    },
                )
            ]
        )
        transport = GoogleHttpGeocodeTransport(sender=sender, now=lambda: NOW)

        result = asyncio.run(
            transport.geocode(GoogleGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT))
        )

        self.assertEqual(result, GoogleGeocodeResponse(Coordinates(51.2, 4.3)))
        self.assertEqual(
            sender.requests,
            [
                InjectedHttpRequest(
                    method="GET",
                    url=GOOGLE_GEOCODING_ENDPOINT,
                    headers=(("Accept", "application/json"),),
                    query=(("address", PRIVATE_TEXT), ("key", PRIVATE_KEY)),
                    json_body=None,
                )
            ],
        )
        request = sender.requests[0]
        self.assertNotIn(PRIVATE_KEY, request.url)
        self.assertNotIn(PRIVATE_KEY, repr(request))
        self.assertNotIn(PRIVATE_TEXT, repr(request))

    def test_geocode_http_status_and_sender_failures_map_without_details(
        self,
    ) -> None:
        cases = (
            (InjectedHttpResponse(400, {}), EventLocationFailureCategory.INVALID_INPUT),
            (InjectedHttpResponse(404, {}), EventLocationFailureCategory.NOT_FOUND),
            (InjectedHttpResponse(429, {}), EventLocationFailureCategory.RATE_LIMITED),
            (
                InjectedHttpResponse(401, {}),
                EventLocationFailureCategory.QUOTA_EXCEEDED,
            ),
            (
                InjectedHttpResponse(403, {}),
                EventLocationFailureCategory.QUOTA_EXCEEDED,
            ),
            (InjectedHttpResponse(503, {}), EventLocationFailureCategory.TRANSIENT),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.TRANSIENT),
                EventLocationFailureCategory.TRANSIENT,
            ),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE),
                EventLocationFailureCategory.UNAVAILABLE,
            ),
        )
        for sender_result, expected in cases:
            with self.subTest(sender_result=sender_result, expected=expected):
                sender = SyntheticHttpSender([sender_result])
                result = asyncio.run(
                    GoogleHttpGeocodeTransport(sender=sender, now=lambda: NOW).geocode(
                        GoogleGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT)
                    )
                )
                self.assertEqual(result, GoogleGeocodeFailure(expected, NOW))
                self.assertNotIn("private", repr(result))

    def test_geocode_provider_statuses_map_without_error_details(self) -> None:
        cases = (
            ("ZERO_RESULTS", EventLocationFailureCategory.NOT_FOUND),
            ("OVER_DAILY_LIMIT", EventLocationFailureCategory.QUOTA_EXCEEDED),
            ("OVER_QUERY_LIMIT", EventLocationFailureCategory.QUOTA_EXCEEDED),
            ("REQUEST_DENIED", EventLocationFailureCategory.QUOTA_EXCEEDED),
            ("INVALID_REQUEST", EventLocationFailureCategory.INVALID_INPUT),
            ("UNKNOWN_ERROR", EventLocationFailureCategory.TRANSIENT),
            ("UNRECOGNIZED", EventLocationFailureCategory.UNAVAILABLE),
        )
        for status, expected in cases:
            with self.subTest(status=status, expected=expected):
                sender = SyntheticHttpSender(
                    [
                        InjectedHttpResponse(
                            200,
                            {"status": status, "error_message": "private echo"},
                        )
                    ]
                )
                result = asyncio.run(
                    GoogleHttpGeocodeTransport(sender=sender, now=lambda: NOW).geocode(
                        GoogleGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT)
                    )
                )
                self.assertEqual(result, GoogleGeocodeFailure(expected, NOW))
                self.assertNotIn("private", repr(result))

    def test_geocode_empty_and_malformed_successes_fail_closed(self) -> None:
        cases = (
            (
                {"status": "OK", "results": []},
                EventLocationFailureCategory.NOT_FOUND,
            ),
            ({}, EventLocationFailureCategory.UNAVAILABLE),
            (
                {
                    "status": "OK",
                    "results": [{"geometry": {"location": {"lat": "bad", "lng": 4.3}}}],
                },
                EventLocationFailureCategory.UNAVAILABLE,
            ),
            (
                {
                    "status": "OK",
                    "results": [{"geometry": {"location": {"lat": 91.0, "lng": 4.3}}}],
                },
                EventLocationFailureCategory.UNAVAILABLE,
            ),
            (
                {
                    "status": "OK",
                    "results": [
                        {"geometry": {"location": {"lat": 51.2, "lng": 181.0}}}
                    ],
                },
                EventLocationFailureCategory.UNAVAILABLE,
            ),
            (
                {"status": "OK", "results": "not-a-list"},
                EventLocationFailureCategory.UNAVAILABLE,
            ),
            (
                {"status": "OK", "results": [{"geometry": {"location": {}}}]},
                EventLocationFailureCategory.UNAVAILABLE,
            ),
        )
        for body, expected in cases:
            with self.subTest(body=body, expected=expected):
                sender = SyntheticHttpSender([InjectedHttpResponse(200, body)])
                result = asyncio.run(
                    GoogleHttpGeocodeTransport(sender=sender, now=lambda: NOW).geocode(
                        GoogleGeocodeQuery(PRIVATE_KEY, PRIVATE_TEXT)
                    )
                )
                self.assertEqual(result, GoogleGeocodeFailure(expected, NOW))


class GoogleRoutesHttpTransportTests(unittest.TestCase):
    def test_route_shapes_exact_post_recipient_and_conservative_body(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "routes": [
                            {
                                "distanceMeters": "12345.6",
                                "duration": "1234.7s",
                                "polyline": {"encodedPolyline": "private echo"},
                            }
                        ]
                    },
                )
            ]
        )
        transport = GoogleHttpRouteTransport(
            sender=sender, api_key=PRIVATE_KEY, now=lambda: NOW
        )
        query = GoogleRoutesQuery(
            origin=ORIGIN,
            destination=DESTINATION,
            avoid_tolls=True,
            avoid_highways=True,
            depart_at=NOW,
        )

        result = asyncio.run(transport.compute_route(query))

        self.assertEqual(result, GoogleRoutesResponse(12_346, 1_235, NOW))
        self.assertEqual(
            sender.requests,
            [
                InjectedHttpRequest(
                    method="POST",
                    url=GOOGLE_ROUTING_ENDPOINT,
                    headers=(
                        ("Accept", "application/json"),
                        ("Content-Type", "application/json"),
                        ("X-Goog-Api-Key", PRIVATE_KEY),
                        (
                            "X-Goog-FieldMask",
                            "routes.distanceMeters,routes.duration",
                        ),
                    ),
                    query=(),
                    json_body={
                        "origin": {
                            "location": {"latLng": {"latitude": 51.0, "longitude": 4.0}}
                        },
                        "destination": {
                            "location": {"latLng": {"latitude": 51.2, "longitude": 4.3}}
                        },
                        "travelMode": "DRIVE",
                        "routingPreference": "TRAFFIC_AWARE",
                        "routeModifiers": {"avoidTolls": True, "avoidHighways": True},
                        "departureTime": "2033-05-06T07:08:09Z",
                    },
                )
            ],
        )
        self.assertNotIn(PRIVATE_KEY, repr(sender.requests[0]))

    def test_route_without_departure_or_modifiers_omits_those_fields(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {"routes": [{"distanceMeters": "4000", "duration": "500s"}]},
                )
            ]
        )
        transport = GoogleHttpRouteTransport(
            sender=sender, api_key=PRIVATE_KEY, now=lambda: NOW
        )

        result = asyncio.run(
            transport.compute_route(
                GoogleRoutesQuery(
                    origin=ORIGIN,
                    destination=DESTINATION,
                    avoid_tolls=False,
                    avoid_highways=False,
                    depart_at=None,
                )
            )
        )

        self.assertEqual(result, GoogleRoutesResponse(4_000, 500, NOW))
        self.assertEqual(
            sender.requests[0].json_body,
            {
                "origin": {
                    "location": {"latLng": {"latitude": 51.0, "longitude": 4.0}}
                },
                "destination": {
                    "location": {"latLng": {"latitude": 51.2, "longitude": 4.3}}
                },
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
            },
        )

    def test_route_http_status_and_sender_failures_map_without_details(self) -> None:
        cases = (
            (InjectedHttpResponse(400, {}), RouteFailureCategory.INVALID_INPUT),
            (
                InjectedHttpResponse(404, {}),
                RouteFailureCategory.UNAVAILABLE,
            ),
            (InjectedHttpResponse(429, {}), RouteFailureCategory.RATE_LIMITED),
            (InjectedHttpResponse(401, {}), RouteFailureCategory.QUOTA_EXCEEDED),
            (InjectedHttpResponse(503, {}), RouteFailureCategory.TRANSIENT),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.TRANSIENT),
                RouteFailureCategory.TRANSIENT,
            ),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE),
                RouteFailureCategory.UNAVAILABLE,
            ),
        )
        for sender_result, expected in cases:
            with self.subTest(sender_result=sender_result, expected=expected):
                sender = SyntheticHttpSender([sender_result])
                result = asyncio.run(
                    GoogleHttpRouteTransport(
                        sender=sender, api_key=PRIVATE_KEY, now=lambda: NOW
                    ).compute_route(
                        GoogleRoutesQuery(
                            origin=ORIGIN,
                            destination=DESTINATION,
                            avoid_tolls=False,
                            avoid_highways=False,
                            depart_at=None,
                        )
                    )
                )
                self.assertEqual(result, GoogleRoutesFailure(expected, NOW))
                self.assertNotIn("private", repr(result))

    def test_route_empty_and_malformed_successes_fail_closed(self) -> None:
        cases = (
            ({"routes": []}, RouteFailureCategory.UNAVAILABLE),
            ({"routes": []}, RouteFailureCategory.UNAVAILABLE),
            (
                {"routes": [{"distanceMeters": "0", "duration": "500s"}]},
                RouteFailureCategory.UNAVAILABLE,
            ),
            (
                {"routes": [{"distanceMeters": "4000", "duration": "bad"}]},
                RouteFailureCategory.UNAVAILABLE,
            ),
            (
                {"routes": [{"distanceMeters": "-4000", "duration": "500s"}]},
                RouteFailureCategory.UNAVAILABLE,
            ),
            ({"routes": {"nope": True}}, RouteFailureCategory.UNAVAILABLE),
            ({}, RouteFailureCategory.UNAVAILABLE),
        )
        for body, expected in cases:
            with self.subTest(body=body, expected=expected):
                sender = SyntheticHttpSender([InjectedHttpResponse(200, body)])
                result = asyncio.run(
                    GoogleHttpRouteTransport(
                        sender=sender, api_key=PRIVATE_KEY, now=lambda: NOW
                    ).compute_route(
                        GoogleRoutesQuery(
                            origin=ORIGIN,
                            destination=DESTINATION,
                            avoid_tolls=False,
                            avoid_highways=False,
                            depart_at=None,
                        )
                    )
                )
                self.assertEqual(result, GoogleRoutesFailure(expected, NOW))


if __name__ == "__main__":
    unittest.main()
