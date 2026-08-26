from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    DeterministicRouteProvider,
    InMemoryRouteCache,
    LocationProvenance,
    ResolvedLocation,
    Route,
    RouteCachePolicy,
    RouteFailure,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteResultSource,
    RouteSuccess,
    build_route_cache_key,
    route_with_cache,
)

NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
PRIVACY_KEY = b"synthetic-profile-key-material"
PROVIDER_NAMESPACE = "deterministic-fake:v1"


def location(endpoint_id: str, latitude: float, longitude: float) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id=endpoint_id,
        coordinates=Coordinates(latitude, longitude),
        provenance=LocationProvenance.ZONE,
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


def request(
    origin: ResolvedLocation,
    destination: ResolvedLocation,
    *,
    avoid_tolls: bool = False,
) -> RouteRequest:
    return RouteRequest(
        origin=origin,
        destination=destination,
        options=RouteOptions(
            avoid_tolls=avoid_tolls,
            avoid_highways=False,
        ),
        depart_at=NOW + timedelta(hours=1),
    )


def successful_route(route_request: RouteRequest, observed_at: datetime = NOW) -> Route:
    return Route(
        origin=route_request.origin,
        destination=route_request.destination,
        distance_m=12_000,
        duration_s=1_200,
        provider="deterministic-fake",
        observed_at=observed_at,
        quality=DataQuality.COMPLETE,
    )


def fake_provider(
    responses: dict[RouteRequest, RouteSuccess | RouteFailure],
) -> DeterministicRouteProvider:
    return DeterministicRouteProvider(PROVIDER_NAMESPACE, responses)


class RouteContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.a = location("synthetic:a", 40.0, -10.0)
        self.b = location("synthetic:b", 41.0, -11.0)

    def test_cache_key_is_directional_private_and_option_sensitive(self) -> None:
        outbound = request(self.a, self.b)
        reverse = request(self.b, self.a)
        avoid_tolls = request(self.a, self.b, avoid_tolls=True)

        outbound_key = build_route_cache_key(
            outbound, PRIVACY_KEY, PROVIDER_NAMESPACE
        )
        self.assertNotEqual(
            outbound_key,
            build_route_cache_key(reverse, PRIVACY_KEY, PROVIDER_NAMESPACE),
        )
        self.assertNotEqual(
            outbound_key,
            build_route_cache_key(avoid_tolls, PRIVACY_KEY, PROVIDER_NAMESPACE),
        )
        self.assertNotEqual(
            outbound_key,
            build_route_cache_key(
                outbound,
                b"another-synthetic-profile-key",
                PROVIDER_NAMESPACE,
            ),
        )
        self.assertNotEqual(
            outbound_key,
            build_route_cache_key(outbound, PRIVACY_KEY, "other-provider:v1"),
        )

        rendered = repr(outbound_key)
        for private_value in ("40.0", "-10.0", "41.0", "-11.0", "synthetic:a"):
            self.assertNotIn(private_value, rendered)
        self.assertNotIn("synthetic:a", repr(outbound))

    def test_request_and_policy_reject_ambiguous_or_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            request(self.a, self.a)
        with self.assertRaises(ValueError):
            RouteRequest(
                origin=self.a,
                destination=self.b,
                options=RouteOptions(False, False),
                depart_at=NOW.replace(tzinfo=None),
            )
        with self.assertRaises(ValueError):
            RouteCachePolicy(timedelta(0), timedelta(hours=1))
        with self.assertRaises(ValueError):
            RouteCachePolicy(timedelta(hours=2), timedelta(hours=1))
        with self.assertRaises(ValueError):
            build_route_cache_key(
                request(self.a, self.b), b"short", PROVIDER_NAMESPACE
            )

    def test_failure_is_typed_retryable_and_privacy_safe(self) -> None:
        transient = RouteFailure(
            category=RouteFailureCategory.TRANSIENT,
            provider="deterministic-fake",
            occurred_at=NOW,
        )
        invalid = RouteFailure(
            category=RouteFailureCategory.INVALID_INPUT,
            provider="deterministic-fake",
            occurred_at=NOW,
        )

        self.assertTrue(transient.retryable)
        self.assertFalse(invalid.retryable)
        self.assertNotIn("coordinates", repr(transient))


class CachedRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.a = location("synthetic:a", 40.0, -10.0)
        self.b = location("synthetic:b", 41.0, -11.0)
        self.route_request = request(self.a, self.b)
        self.route = successful_route(self.route_request)
        self.policy = RouteCachePolicy(
            maximum_fresh_age=timedelta(minutes=30),
            maximum_stale_age=timedelta(hours=2),
        )

    async def test_fake_is_exact_directional_and_never_calls_a_network(self) -> None:
        reverse = request(self.b, self.a)
        unavailable = RouteFailure(
            RouteFailureCategory.UNAVAILABLE,
            "deterministic-fake",
            NOW,
        )
        provider = fake_provider(
            {self.route_request: RouteSuccess(self.route), reverse: unavailable}
        )

        self.assertEqual(
            await provider.route(self.route_request),
            RouteSuccess(self.route),
        )
        self.assertEqual(await provider.route(reverse), unavailable)
        self.assertEqual(provider.requests, (self.route_request, reverse))

    async def test_fresh_cache_hit_skips_provider(self) -> None:
        provider = fake_provider({})
        cache = InMemoryRouteCache()
        key = build_route_cache_key(
            self.route_request, PRIVACY_KEY, PROVIDER_NAMESPACE
        )
        await cache.put(key, self.route, NOW)

        result = await route_with_cache(
            request=self.route_request,
            provider=provider,
            cache=cache,
            policy=self.policy,
            privacy_key=PRIVACY_KEY,
            evaluated_at=NOW + timedelta(minutes=30),
        )

        self.assertEqual(result, RouteSuccess(self.route, RouteResultSource.CACHE))
        self.assertEqual(provider.requests, ())

    async def test_stale_cache_falls_back_only_when_refresh_fails(self) -> None:
        stale_time = NOW + timedelta(minutes=31)
        failure = RouteFailure(
            RouteFailureCategory.RATE_LIMITED,
            "deterministic-fake",
            stale_time,
        )
        provider = fake_provider({self.route_request: failure})
        cache = InMemoryRouteCache()
        key = build_route_cache_key(
            self.route_request, PRIVACY_KEY, PROVIDER_NAMESPACE
        )
        await cache.put(key, self.route, NOW)

        result = await route_with_cache(
            request=self.route_request,
            provider=provider,
            cache=cache,
            policy=self.policy,
            privacy_key=PRIVACY_KEY,
            evaluated_at=stale_time,
        )

        assert isinstance(result, RouteSuccess)
        self.assertEqual(result.source, RouteResultSource.STALE_CACHE)
        self.assertEqual(result.route.quality, DataQuality.STALE)
        self.assertEqual(result.refresh_failure, RouteFailureCategory.RATE_LIMITED)

    async def test_refresh_replaces_stale_and_expired_failure_is_explicit(
        self,
    ) -> None:
        cache = InMemoryRouteCache()
        key = build_route_cache_key(
            self.route_request, PRIVACY_KEY, PROVIDER_NAMESPACE
        )
        await cache.put(key, self.route, NOW)
        refreshed = successful_route(
            self.route_request,
            NOW + timedelta(minutes=31),
        )
        provider = fake_provider(
            {self.route_request: RouteSuccess(refreshed)}
        )

        refresh_result = await route_with_cache(
            request=self.route_request,
            provider=provider,
            cache=cache,
            policy=self.policy,
            privacy_key=PRIVACY_KEY,
            evaluated_at=NOW + timedelta(minutes=31),
        )
        self.assertEqual(
            refresh_result,
            RouteSuccess(refreshed, RouteResultSource.PROVIDER),
        )

        expired_cache = InMemoryRouteCache()
        await expired_cache.put(key, self.route, NOW)
        failure = RouteFailure(
            RouteFailureCategory.TRANSIENT,
            "deterministic-fake",
            NOW + timedelta(hours=2, seconds=1),
        )
        failing_provider = fake_provider({self.route_request: failure})
        expired_result = await route_with_cache(
            request=self.route_request,
            provider=failing_provider,
            cache=expired_cache,
            policy=self.policy,
            privacy_key=PRIVACY_KEY,
            evaluated_at=NOW + timedelta(hours=2, seconds=1),
        )
        self.assertEqual(expired_result, failure)

    async def test_cache_rejects_future_evaluation_and_provider_mismatch(self) -> None:
        cache = InMemoryRouteCache()
        key = build_route_cache_key(
            self.route_request, PRIVACY_KEY, PROVIDER_NAMESPACE
        )
        await cache.put(key, self.route, NOW)
        provider = fake_provider({})
        with self.assertRaises(ValueError):
            await route_with_cache(
                request=self.route_request,
                provider=provider,
                cache=cache,
                policy=self.policy,
                privacy_key=PRIVACY_KEY,
                evaluated_at=NOW - timedelta(seconds=1),
            )

        wrong_direction = successful_route(request(self.b, self.a))
        corrupted_cache = InMemoryRouteCache()
        await corrupted_cache.put(key, wrong_direction, NOW)
        with self.assertRaises(ValueError):
            await route_with_cache(
                request=self.route_request,
                provider=provider,
                cache=corrupted_cache,
                policy=self.policy,
                privacy_key=PRIVACY_KEY,
                evaluated_at=NOW,
            )

        mismatched_provider = fake_provider(
            {self.route_request: RouteSuccess(wrong_direction)}
        )
        empty_cache = InMemoryRouteCache()
        with self.assertRaises(ValueError):
            await route_with_cache(
                request=self.route_request,
                provider=mismatched_provider,
                cache=empty_cache,
                policy=self.policy,
                privacy_key=PRIVACY_KEY,
                evaluated_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
