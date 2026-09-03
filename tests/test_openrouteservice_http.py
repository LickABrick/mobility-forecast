from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime

from custom_components.mobility_forecast.domain import (
    Coordinates,
    EventLocationFailureCategory,
    RouteFailureCategory,
)
from custom_components.mobility_forecast.openrouteservice import (
    ORS_HOSTED_GEOCODING_ENDPOINT,
    ORS_HOSTED_ROUTING_ENDPOINT,
    OpenRouteServiceGeocodeFailure,
    OpenRouteServiceGeocodeQuery,
    OpenRouteServiceGeocodeResponse,
    OpenRouteServiceRouteFailure,
    OpenRouteServiceRouteQuery,
    OpenRouteServiceRouteResponse,
)
from custom_components.mobility_forecast.openrouteservice_http import (
    InjectedHttpFailure,
    InjectedHttpFailureCategory,
    InjectedHttpRequest,
    InjectedHttpResponse,
    OpenRouteServiceHttpGeocodeTransport,
    OpenRouteServiceHttpRouteTransport,
)
from custom_components.mobility_forecast.route_provider_config import GeocoderKind

NOW = datetime(2033, 5, 6, 7, 8, 9, tzinfo=UTC)
PRIVATE_TEXT = "Synthetic Private Destination 42"
PRIVATE_KEY = "synthetic-provider-key"


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


class OpenRouteServiceHttpTransportTests(unittest.TestCase):
    def test_hosted_pelias_uses_fixed_get_recipient_and_header_key(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "features": [
                            {
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [4.3, 51.2],
                                }
                            }
                        ]
                    },
                )
            ]
        )
        transport = OpenRouteServiceHttpGeocodeTransport(sender=sender, now=lambda: NOW)
        query = OpenRouteServiceGeocodeQuery(
            endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
            api_key=PRIVATE_KEY,
            geocoder=GeocoderKind.PELIAS,
            location_text=PRIVATE_TEXT,
        )

        result = asyncio.run(transport.geocode(query))

        self.assertEqual(
            result, OpenRouteServiceGeocodeResponse(Coordinates(51.2, 4.3))
        )
        self.assertEqual(
            sender.requests,
            [
                InjectedHttpRequest(
                    method="GET",
                    url=ORS_HOSTED_GEOCODING_ENDPOINT,
                    headers=(
                        ("Accept", "application/json"),
                        ("Authorization", PRIVATE_KEY),
                    ),
                    query=(("text", PRIVATE_TEXT), ("size", "1")),
                    json_body=None,
                )
            ],
        )
        self.assertNotIn(PRIVATE_KEY, sender.requests[0].url)
        self.assertNotIn(PRIVATE_KEY, repr(sender.requests[0]))
        self.assertNotIn(PRIVATE_TEXT, repr(sender.requests[0]))

    def test_self_hosted_geocoders_use_family_specific_paths_and_decoders(self) -> None:
        cases = (
            (
                GeocoderKind.PELIAS,
                "https://geocoder.synthetic.invalid/pelias/",
                "https://geocoder.synthetic.invalid/pelias/v1/search",
                (("text", PRIVATE_TEXT), ("size", "1")),
                {
                    "features": [
                        {
                            "geometry": {
                                "type": "Point",
                                "coordinates": [5.2, 50.1],
                            }
                        }
                    ]
                },
            ),
            (
                GeocoderKind.PHOTON,
                "https://geocoder.synthetic.invalid/photon",
                "https://geocoder.synthetic.invalid/photon/api",
                (("q", PRIVATE_TEXT), ("limit", "1")),
                {
                    "features": [
                        {
                            "geometry": {
                                "type": "Point",
                                "coordinates": [5.2, 50.1],
                            }
                        }
                    ]
                },
            ),
            (
                GeocoderKind.NOMINATIM,
                "https://geocoder.synthetic.invalid/nominatim",
                "https://geocoder.synthetic.invalid/nominatim/search",
                (("q", PRIVATE_TEXT), ("format", "jsonv2"), ("limit", "1")),
                [{"lat": "50.1", "lon": "5.2"}],
            ),
        )
        for geocoder, base_url, expected_url, expected_query, body in cases:
            with self.subTest(geocoder=geocoder):
                sender = SyntheticHttpSender([InjectedHttpResponse(200, body)])
                transport = OpenRouteServiceHttpGeocodeTransport(
                    sender=sender, now=lambda: NOW
                )

                result = asyncio.run(
                    transport.geocode(
                        OpenRouteServiceGeocodeQuery(
                            endpoint=base_url,
                            api_key=None,
                            geocoder=geocoder,
                            location_text=PRIVATE_TEXT,
                        )
                    )
                )

                self.assertEqual(
                    result,
                    OpenRouteServiceGeocodeResponse(Coordinates(50.1, 5.2)),
                )
                self.assertEqual(sender.requests[0].url, expected_url)
                self.assertEqual(sender.requests[0].query, expected_query)
                self.assertEqual(
                    sender.requests[0].headers, (("Accept", "application/json"),)
                )

    def test_route_shapes_exact_ors_post_and_decodes_conservatively(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "routes": [
                            {
                                "summary": {
                                    "distance": 12_345.1,
                                    "duration": 1_234.01,
                                }
                            }
                        ]
                    },
                )
            ]
        )
        transport = OpenRouteServiceHttpRouteTransport(sender=sender, now=lambda: NOW)
        query = OpenRouteServiceRouteQuery(
            endpoint=ORS_HOSTED_ROUTING_ENDPOINT,
            api_key=PRIVATE_KEY,
            origin=Coordinates(51.0, 4.0),
            destination=Coordinates(51.2, 4.3),
            avoid_tolls=True,
            avoid_highways=True,
            depart_at=NOW,
        )

        result = asyncio.run(transport.route(query))

        self.assertEqual(result, OpenRouteServiceRouteResponse(12_346, 1_235, NOW))
        self.assertEqual(
            sender.requests,
            [
                InjectedHttpRequest(
                    method="POST",
                    url=ORS_HOSTED_ROUTING_ENDPOINT,
                    headers=(
                        ("Accept", "application/json"),
                        ("Content-Type", "application/json"),
                        ("Authorization", PRIVATE_KEY),
                    ),
                    query=(),
                    json_body={
                        "coordinates": [[4.0, 51.0], [4.3, 51.2]],
                        "geometry": False,
                        "instructions": False,
                        "units": "m",
                        "departure": "2033-05-06T07:08:09",
                        "options": {"avoid_features": ["tollways", "highways"]},
                    },
                )
            ],
        )

    def test_self_hosted_route_appends_ors_path_without_credentials(self) -> None:
        sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {"routes": [{"summary": {"distance": 4000, "duration": 500}}]},
                )
            ]
        )
        transport = OpenRouteServiceHttpRouteTransport(sender=sender, now=lambda: NOW)

        result = asyncio.run(
            transport.route(
                OpenRouteServiceRouteQuery(
                    endpoint="https://routing.synthetic.invalid/ors/",
                    api_key=None,
                    origin=Coordinates(50.0, 5.0),
                    destination=Coordinates(50.1, 5.2),
                    avoid_tolls=False,
                    avoid_highways=False,
                    depart_at=None,
                )
            )
        )

        self.assertEqual(result, OpenRouteServiceRouteResponse(4000, 500, NOW))
        request = sender.requests[0]
        self.assertEqual(
            request.url,
            "https://routing.synthetic.invalid/ors/v2/directions/driving-car",
        )
        self.assertEqual(
            request.headers,
            (("Accept", "application/json"), ("Content-Type", "application/json")),
        )
        self.assertEqual(
            request.json_body,
            {
                "coordinates": [[5.0, 50.0], [5.2, 50.1]],
                "geometry": False,
                "instructions": False,
                "units": "m",
            },
        )

    def test_http_status_and_sender_failures_map_without_response_details(self) -> None:
        geocode_cases = (
            (
                InjectedHttpResponse(400, {"error": "private echo"}),
                EventLocationFailureCategory.INVALID_INPUT,
            ),
            (InjectedHttpResponse(429, {}), EventLocationFailureCategory.RATE_LIMITED),
            (InjectedHttpResponse(503, {}), EventLocationFailureCategory.TRANSIENT),
            (InjectedHttpResponse(401, {}), EventLocationFailureCategory.UNAVAILABLE),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.TRANSIENT),
                EventLocationFailureCategory.TRANSIENT,
            ),
            (
                InjectedHttpFailure(InjectedHttpFailureCategory.UNAVAILABLE),
                EventLocationFailureCategory.UNAVAILABLE,
            ),
        )
        for sender_result, expected in geocode_cases:
            with self.subTest(sender_result=sender_result, expected=expected):
                sender = SyntheticHttpSender([sender_result])
                result = asyncio.run(
                    OpenRouteServiceHttpGeocodeTransport(
                        sender=sender, now=lambda: NOW
                    ).geocode(
                        OpenRouteServiceGeocodeQuery(
                            endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
                            api_key=PRIVATE_KEY,
                            geocoder=GeocoderKind.PELIAS,
                            location_text=PRIVATE_TEXT,
                        )
                    )
                )
                self.assertEqual(result, OpenRouteServiceGeocodeFailure(expected, NOW))
                self.assertNotIn("private echo", repr(result))

        route_sender = SyntheticHttpSender([InjectedHttpResponse(422, {})])
        route_result = asyncio.run(
            OpenRouteServiceHttpRouteTransport(
                sender=route_sender, now=lambda: NOW
            ).route(
                OpenRouteServiceRouteQuery(
                    endpoint=ORS_HOSTED_ROUTING_ENDPOINT,
                    api_key=PRIVATE_KEY,
                    origin=Coordinates(51.0, 4.0),
                    destination=Coordinates(51.2, 4.3),
                    avoid_tolls=False,
                    avoid_highways=False,
                    depart_at=None,
                )
            )
        )
        self.assertEqual(
            route_result,
            OpenRouteServiceRouteFailure(RouteFailureCategory.INVALID_INPUT, NOW),
        )

    def test_empty_and_malformed_successes_fail_closed(self) -> None:
        empty_sender = SyntheticHttpSender(
            [InjectedHttpResponse(200, {"features": []})]
        )
        empty = asyncio.run(
            OpenRouteServiceHttpGeocodeTransport(
                sender=empty_sender, now=lambda: NOW
            ).geocode(
                OpenRouteServiceGeocodeQuery(
                    endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
                    api_key=PRIVATE_KEY,
                    geocoder=GeocoderKind.PELIAS,
                    location_text=PRIVATE_TEXT,
                )
            )
        )
        self.assertEqual(
            empty,
            OpenRouteServiceGeocodeFailure(EventLocationFailureCategory.NOT_FOUND, NOW),
        )

        malformed_geocode_sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {
                        "features": [
                            {
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [True, 51.2],
                                }
                            }
                        ]
                    },
                )
            ]
        )
        malformed_geocode = asyncio.run(
            OpenRouteServiceHttpGeocodeTransport(
                sender=malformed_geocode_sender, now=lambda: NOW
            ).geocode(
                OpenRouteServiceGeocodeQuery(
                    endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
                    api_key=PRIVATE_KEY,
                    geocoder=GeocoderKind.PELIAS,
                    location_text=PRIVATE_TEXT,
                )
            )
        )
        self.assertEqual(
            malformed_geocode,
            OpenRouteServiceGeocodeFailure(
                EventLocationFailureCategory.UNAVAILABLE, NOW
            ),
        )

        malformed_route_sender = SyntheticHttpSender(
            [
                InjectedHttpResponse(
                    200,
                    {"routes": [{"summary": {"distance": 0, "duration": 500}}]},
                )
            ]
        )
        malformed_route = asyncio.run(
            OpenRouteServiceHttpRouteTransport(
                sender=malformed_route_sender, now=lambda: NOW
            ).route(
                OpenRouteServiceRouteQuery(
                    endpoint=ORS_HOSTED_ROUTING_ENDPOINT,
                    api_key=PRIVATE_KEY,
                    origin=Coordinates(51.0, 4.0),
                    destination=Coordinates(51.2, 4.3),
                    avoid_tolls=False,
                    avoid_highways=False,
                    depart_at=None,
                )
            )
        )
        self.assertEqual(
            malformed_route,
            OpenRouteServiceRouteFailure(RouteFailureCategory.UNAVAILABLE, NOW),
        )

    def test_credentials_cannot_cross_hosted_and_self_hosted_boundaries(self) -> None:
        cases = (
            OpenRouteServiceGeocodeQuery(
                endpoint="https://geocoder.synthetic.invalid/pelias",
                api_key=PRIVATE_KEY,
                geocoder=GeocoderKind.PELIAS,
                location_text=PRIVATE_TEXT,
            ),
            OpenRouteServiceGeocodeQuery(
                endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
                api_key=None,
                geocoder=GeocoderKind.PELIAS,
                location_text=PRIVATE_TEXT,
            ),
            OpenRouteServiceGeocodeQuery(
                endpoint=ORS_HOSTED_GEOCODING_ENDPOINT,
                api_key=PRIVATE_KEY,
                geocoder=GeocoderKind.PHOTON,
                location_text=PRIVATE_TEXT,
            ),
        )
        for query in cases:
            with self.subTest(query=query):
                sender = SyntheticHttpSender([])
                transport = OpenRouteServiceHttpGeocodeTransport(
                    sender=sender, now=lambda: NOW
                )
                with self.assertRaisesRegex(ValueError, "hosted geocoding"):
                    asyncio.run(transport.geocode(query))
                self.assertEqual(sender.requests, [])

        route_cases = (
            ("https://routing.synthetic.invalid/ors", PRIVATE_KEY),
            (ORS_HOSTED_ROUTING_ENDPOINT, None),
        )
        for endpoint, api_key in route_cases:
            with self.subTest(endpoint=endpoint, api_key=api_key):
                sender = SyntheticHttpSender([])
                transport = OpenRouteServiceHttpRouteTransport(
                    sender=sender, now=lambda: NOW
                )
                with self.assertRaisesRegex(ValueError, "hosted routing"):
                    asyncio.run(
                        transport.route(
                            OpenRouteServiceRouteQuery(
                                endpoint=endpoint,
                                api_key=api_key,
                                origin=Coordinates(51.0, 4.0),
                                destination=Coordinates(51.2, 4.3),
                                avoid_tolls=False,
                                avoid_highways=False,
                                depart_at=None,
                            )
                        )
                    )
                self.assertEqual(sender.requests, [])

    def test_http_value_representations_hide_private_payloads(self) -> None:
        request = InjectedHttpRequest(
            method="GET",
            url="https://private.synthetic.invalid/search",
            headers=(("Authorization", PRIVATE_KEY),),
            query=(("text", PRIVATE_TEXT),),
            json_body={"private": PRIVATE_TEXT},
        )
        response = InjectedHttpResponse(400, {"error": PRIVATE_TEXT})

        rendered = repr((request, response))

        for private_value in (
            "private.synthetic.invalid",
            PRIVATE_KEY,
            PRIVATE_TEXT,
        ):
            self.assertNotIn(private_value, rendered)


if __name__ == "__main__":
    unittest.main()
