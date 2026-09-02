from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    LocationProvenance,
    ResolvedLocation,
    RouteFailure,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteSuccess,
)
from custom_components.mobility_forecast.google_routes import (
    GOOGLE_ROUTES_CACHE_NAMESPACE,
    GOOGLE_ROUTES_PROVIDER,
    GoogleRoutesAdapter,
    GoogleRoutesFailure,
    GoogleRoutesQuery,
    GoogleRoutesResponse,
)

NOW = datetime(2032, 4, 5, 7, 0, tzinfo=UTC)


def location(endpoint_id: str, latitude: float, longitude: float) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id=endpoint_id,
        coordinates=Coordinates(latitude, longitude),
        provenance=LocationProvenance.ZONE,
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


class SyntheticGoogleRoutesTransport:
    def __init__(self, response: GoogleRoutesResponse | GoogleRoutesFailure) -> None:
        self.response = response
        self.queries: list[GoogleRoutesQuery] = []

    async def compute_route(
        self, query: GoogleRoutesQuery
    ) -> GoogleRoutesResponse | GoogleRoutesFailure:
        self.queries.append(query)
        return self.response


class GoogleRoutesAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.origin = location("synthetic-origin", 51.0, 4.0)
        self.destination = location("synthetic-destination", 51.1, 4.2)
        self.request = RouteRequest(
            origin=self.origin,
            destination=self.destination,
            options=RouteOptions(avoid_tolls=True, avoid_highways=False),
            depart_at=NOW,
        )

    def test_maps_provider_neutral_request_and_synthetic_success(self) -> None:
        transport = SyntheticGoogleRoutesTransport(
            GoogleRoutesResponse(distance_m=12_345, duration_s=1_234, observed_at=NOW)
        )
        adapter = GoogleRoutesAdapter(transport)

        result = asyncio.run(adapter.route(self.request))

        self.assertEqual(adapter.cache_namespace, GOOGLE_ROUTES_CACHE_NAMESPACE)
        self.assertEqual(
            transport.queries,
            [
                GoogleRoutesQuery(
                    origin=self.origin.coordinates,
                    destination=self.destination.coordinates,
                    avoid_tolls=True,
                    avoid_highways=False,
                    depart_at=NOW,
                )
            ],
        )
        self.assertEqual(
            result,
            RouteSuccess(
                route=result.route,  # type: ignore[union-attr]
            ),
        )
        self.assertEqual(result.route.origin, self.origin)  # type: ignore[union-attr]
        self.assertEqual(result.route.destination, self.destination)  # type: ignore[union-attr]
        self.assertEqual(result.route.distance_m, 12_345)  # type: ignore[union-attr]
        self.assertEqual(result.route.duration_s, 1_234)  # type: ignore[union-attr]
        self.assertEqual(result.route.provider, GOOGLE_ROUTES_PROVIDER)  # type: ignore[union-attr]
        self.assertEqual(result.route.quality, DataQuality.COMPLETE)  # type: ignore[union-attr]

    def test_maps_synthetic_transport_failure_without_response_text(self) -> None:
        transport = SyntheticGoogleRoutesTransport(
            GoogleRoutesFailure(
                category=RouteFailureCategory.QUOTA_EXCEEDED,
                occurred_at=NOW,
            )
        )
        adapter = GoogleRoutesAdapter(transport)

        result = asyncio.run(adapter.route(self.request))

        self.assertEqual(
            result,
            RouteFailure(
                category=RouteFailureCategory.QUOTA_EXCEEDED,
                provider=GOOGLE_ROUTES_PROVIDER,
                occurred_at=NOW,
            ),
        )

    def test_query_representation_omits_coordinates(self) -> None:
        query = GoogleRoutesQuery(
            origin=self.origin.coordinates,
            destination=self.destination.coordinates,
            avoid_tolls=False,
            avoid_highways=True,
            depart_at=None,
        )

        rendered = repr(query)
        self.assertNotIn("51.0", rendered)
        self.assertNotIn("51.1", rendered)
        self.assertNotIn("4.2", rendered)

    def test_rejects_invalid_synthetic_transport_values(self) -> None:
        invalid_values = (
            (0, 100),
            (100, 0),
            (True, 100),
        )

        for distance_m, duration_s in invalid_values:
            with (
                self.subTest(distance_m=distance_m, duration_s=duration_s),
                self.assertRaises(ValueError),
            ):
                GoogleRoutesResponse(
                    distance_m=distance_m,
                    duration_s=duration_s,
                    observed_at=NOW,
                )


if __name__ == "__main__":
    unittest.main()
