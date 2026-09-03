from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.domain.models import (
    Coordinates,
    DataQuality,
    LocationProvenance,
    ResolvedLocation,
    Route,
)
from custom_components.mobility_forecast.domain.routing import (
    RouteCacheEntry,
    RouteCacheKey,
)
from custom_components.mobility_forecast.openrouteservice import GeocodeCacheEntry
from custom_components.mobility_forecast.provider_cache_storage import (
    PROVIDER_CACHE_STORAGE_SCHEMA_VERSION,
    ProviderCacheState,
    decode_provider_cache_state,
    encode_provider_cache_state,
    provider_cache_storage_key,
    prune_provider_cache_state,
)
from custom_components.mobility_forecast.provider_guardrails import GeocodeCacheKey

NOW = datetime(2034, 2, 3, 10, 0, tzinfo=UTC)
PRIVACY_KEY = bytes(range(32))
GEOCODE_KEY = GeocodeCacheKey("1" * 64)
ROUTE_KEY = RouteCacheKey("2" * 64)


def route() -> Route:
    origin = ResolvedLocation(
        endpoint_id="synthetic:origin",
        coordinates=Coordinates(51.0, 4.0),
        provenance=LocationProvenance.ZONE,
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )
    destination = ResolvedLocation(
        endpoint_id="synthetic:destination",
        coordinates=Coordinates(51.2, 4.3),
        provenance=LocationProvenance.EVENT,
        observed_at=None,
        quality=DataQuality.COMPLETE,
    )
    return Route(
        origin=origin,
        destination=destination,
        distance_m=12_345,
        duration_s=1_234,
        provider="synthetic-provider",
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


def state(*, stored_at: datetime = NOW) -> ProviderCacheState:
    return ProviderCacheState(
        privacy_key=PRIVACY_KEY,
        geocodes=((GEOCODE_KEY, GeocodeCacheEntry(Coordinates(51.2, 4.3), stored_at)),),
        routes=((ROUTE_KEY, RouteCacheEntry(route(), stored_at)),),
    )


class ProviderCacheStorageTests(unittest.TestCase):
    def test_round_trips_versioned_private_cache_state(self) -> None:
        original = state()

        encoded = encode_provider_cache_state(original)
        restored = decode_provider_cache_state(json.loads(json.dumps(encoded)))

        self.assertEqual(encoded["version"], PROVIDER_CACHE_STORAGE_SCHEMA_VERSION)
        self.assertEqual(restored, original)
        self.assertNotIn(PRIVACY_KEY.hex(), json.dumps(encoded))
        self.assertNotIn("synthetic:origin", repr(restored))
        with self.assertRaises(FrozenInstanceError):
            restored.routes = ()  # type: ignore[misc]

    def test_rejects_unknown_versions_duplicate_keys_and_malformed_key_material(
        self,
    ) -> None:
        encoded = encode_provider_cache_state(state())

        with self.assertRaisesRegex(ValueError, "unsupported provider cache schema"):
            decode_provider_cache_state(
                {**encoded, "version": PROVIDER_CACHE_STORAGE_SCHEMA_VERSION + 1}
            )
        with self.assertRaisesRegex(ValueError, "privacy key"):
            decode_provider_cache_state({**encoded, "privacy_key": "invalid"})
        with self.assertRaisesRegex(ValueError, "geocode cache keys"):
            ProviderCacheState(
                PRIVACY_KEY,
                state().geocodes + state().geocodes,
                (),
            )

    def test_prunes_expired_and_future_entries_without_mutating_input(self) -> None:
        expired = state(stored_at=NOW - timedelta(hours=4))
        future = ProviderCacheState(
            PRIVACY_KEY,
            ((GEOCODE_KEY, GeocodeCacheEntry(Coordinates(1.0, 2.0), NOW)),),
            ((ROUTE_KEY, RouteCacheEntry(route(), NOW + timedelta(seconds=1))),),
        )

        pruned_expired = prune_provider_cache_state(
            expired,
            evaluated_at=NOW,
            maximum_geocode_age=timedelta(hours=2),
            maximum_route_age=timedelta(hours=3),
        )
        pruned_future = prune_provider_cache_state(
            future,
            evaluated_at=NOW,
            maximum_geocode_age=timedelta(hours=2),
            maximum_route_age=timedelta(hours=3),
        )

        self.assertEqual(pruned_expired, ProviderCacheState(PRIVACY_KEY, (), ()))
        self.assertEqual(pruned_future.geocodes, future.geocodes)
        self.assertEqual(pruned_future.routes, ())
        self.assertEqual(len(expired.geocodes), 1)

    def test_store_key_is_config_entry_scoped(self) -> None:
        self.assertEqual(
            provider_cache_storage_key("entry-a"),
            "mobility_forecast.provider_cache.entry-a",
        )
        self.assertNotEqual(
            provider_cache_storage_key("entry-a"),
            provider_cache_storage_key("entry-b"),
        )
        with self.assertRaises(ValueError):
            provider_cache_storage_key(" ")


if __name__ == "__main__":
    unittest.main()
