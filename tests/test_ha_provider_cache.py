from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from custom_components.mobility_forecast.domain.models import Coordinates
from custom_components.mobility_forecast.domain.routing import RouteCacheKey
from custom_components.mobility_forecast.provider_cache_storage import (
    PROVIDER_CACHE_STORAGE_SCHEMA_VERSION,
    provider_cache_storage_key,
)
from custom_components.mobility_forecast.provider_guardrails import GeocodeCacheKey
from tests.test_provider_cache_storage import PRIVACY_KEY, route

ADAPTER_MODULE = "custom_components.mobility_forecast.ha_provider_cache"
NOW = datetime(2034, 2, 3, 10, 0, tzinfo=UTC)


class FakeHomeAssistant:
    def __init__(self, backing: dict[str, object] | None = None) -> None:
        self.storage_backing = backing if backing is not None else {}


class FakeStore:
    instances: ClassVar[list[FakeStore]] = []
    fail_next_save: ClassVar[bool] = False

    def __init__(
        self,
        hass: FakeHomeAssistant,
        version: int,
        key: str,
        private: bool = False,
        *,
        atomic_writes: bool = False,
    ) -> None:
        self.hass = hass
        self.version = version
        self.key = key
        self.private = private
        self.atomic_writes = atomic_writes
        self.save_calls = 0
        self.__class__.instances.append(self)

    @classmethod
    def __class_getitem__(cls, item: object) -> type[FakeStore]:
        del item
        return cls

    async def async_load(self) -> object | None:
        value = self.hass.storage_backing.get(self.key)
        return None if value is None else json.loads(json.dumps(value))

    async def async_save(self, data: object) -> None:
        self.save_calls += 1
        if self.__class__.fail_next_save:
            self.__class__.fail_next_save = False
            raise OSError("synthetic atomic save failure")
        self.hass.storage_backing[self.key] = json.loads(json.dumps(data))


@contextmanager
def fake_home_assistant_storage() -> Generator[None]:
    homeassistant = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = FakeHomeAssistant  # type: ignore[attr-defined]
    helpers = types.ModuleType("homeassistant.helpers")
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = FakeStore  # type: ignore[attr-defined]
    modules = {
        "homeassistant": homeassistant,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.storage": storage,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    FakeStore.instances.clear()
    FakeStore.fail_next_save = False
    sys.modules.pop(ADAPTER_MODULE, None)
    try:
        yield
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
        sys.modules.pop(ADAPTER_MODULE, None)


def load_adapter() -> Any:
    return importlib.import_module(ADAPTER_MODULE)


class HomeAssistantProviderCacheTests(unittest.TestCase):
    def test_first_initialization_generates_and_persists_one_profile_key(self) -> None:
        hass = FakeHomeAssistant()

        with fake_home_assistant_storage():
            module = load_adapter()
            caches = module.HomeAssistantProviderCaches(
                hass, "entry-a", generate_privacy_key=lambda: PRIVACY_KEY
            )
            asyncio.run(
                caches.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )

        self.assertEqual(caches.privacy_key, PRIVACY_KEY)
        store = FakeStore.instances[0]
        self.assertEqual(store.version, PROVIDER_CACHE_STORAGE_SCHEMA_VERSION)
        self.assertEqual(store.key, provider_cache_storage_key("entry-a"))
        self.assertTrue(store.private)
        self.assertTrue(store.atomic_writes)
        self.assertEqual(store.save_calls, 1)

    def test_restart_restores_key_and_both_cache_types(self) -> None:
        backing: dict[str, object] = {}
        geocode_key = GeocodeCacheKey("a" * 64)
        route_key = RouteCacheKey("b" * 64)

        with fake_home_assistant_storage():
            module = load_adapter()
            before = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(backing),
                "entry-a",
                generate_privacy_key=lambda: PRIVACY_KEY,
            )
            asyncio.run(
                before.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )
            asyncio.run(
                before.geocode_cache.put(geocode_key, Coordinates(51.2, 4.3), NOW)
            )
            asyncio.run(before.route_cache.put(route_key, route(), NOW))

            after = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(backing),
                "entry-a",
                generate_privacy_key=lambda: b"x" * 32,
            )
            asyncio.run(
                after.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )
            restored_geocode = asyncio.run(after.geocode_cache.get(geocode_key))
            restored_route = asyncio.run(after.route_cache.get(route_key))

        self.assertEqual(after.privacy_key, PRIVACY_KEY)
        self.assertEqual(restored_geocode.coordinates, Coordinates(51.2, 4.3))
        self.assertEqual(restored_route.route, route())

    def test_initialization_prunes_expired_entries_and_isolates_profiles(self) -> None:
        backing: dict[str, object] = {}
        key = GeocodeCacheKey("c" * 64)

        with fake_home_assistant_storage():
            module = load_adapter()
            first = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(backing),
                "entry-a",
                generate_privacy_key=lambda: PRIVACY_KEY,
            )
            asyncio.run(
                first.async_initialize(
                    evaluated_at=NOW - timedelta(hours=4),
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )
            asyncio.run(
                first.geocode_cache.put(
                    key, Coordinates(51.2, 4.3), NOW - timedelta(hours=4)
                )
            )
            restarted = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(backing),
                "entry-a",
                generate_privacy_key=lambda: b"x" * 32,
            )
            asyncio.run(
                restarted.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )
            second = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(backing),
                "entry-b",
                generate_privacy_key=lambda: b"y" * 32,
            )
            asyncio.run(
                second.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )

        self.assertIsNone(asyncio.run(restarted.geocode_cache.get(key)))
        self.assertNotEqual(restarted.privacy_key, second.privacy_key)
        self.assertEqual(
            set(backing),
            {
                provider_cache_storage_key("entry-a"),
                provider_cache_storage_key("entry-b"),
            },
        )

    def test_rotation_replaces_key_and_atomically_clears_both_caches(self) -> None:
        generated = iter((PRIVACY_KEY, b"z" * 32))
        geocode_key = GeocodeCacheKey("d" * 64)
        route_key = RouteCacheKey("f" * 64)

        with fake_home_assistant_storage():
            module = load_adapter()
            caches = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(),
                "entry-a",
                generate_privacy_key=lambda: next(generated),
            )
            asyncio.run(
                caches.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )
            asyncio.run(
                caches.geocode_cache.put(geocode_key, Coordinates(1.0, 2.0), NOW)
            )
            asyncio.run(caches.route_cache.put(route_key, route(), NOW))
            rotated = asyncio.run(caches.async_rotate_privacy_key())

        self.assertEqual(rotated, b"z" * 32)
        self.assertEqual(caches.privacy_key, rotated)
        self.assertIsNone(asyncio.run(caches.geocode_cache.get(geocode_key)))
        self.assertIsNone(asyncio.run(caches.route_cache.get(route_key)))

    def test_failed_atomic_save_does_not_publish_unpersisted_cache_state(self) -> None:
        key = GeocodeCacheKey("e" * 64)

        with fake_home_assistant_storage():
            module = load_adapter()
            caches = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(),
                "entry-a",
                generate_privacy_key=lambda: PRIVACY_KEY,
            )
            asyncio.run(
                caches.async_initialize(
                    evaluated_at=NOW,
                    maximum_geocode_age=timedelta(hours=2),
                    maximum_route_age=timedelta(hours=3),
                )
            )
            FakeStore.fail_next_save = True

            with self.assertRaisesRegex(OSError, "synthetic atomic save failure"):
                asyncio.run(caches.geocode_cache.put(key, Coordinates(1.0, 2.0), NOW))

        self.assertIsNone(asyncio.run(caches.geocode_cache.get(key)))

    def test_malformed_store_fails_closed_without_rotation_or_overwrite(self) -> None:
        key = provider_cache_storage_key("entry-a")
        malformed = {
            "version": 99,
            "privacy_key": "private",
            "geocodes": [],
            "routes": [],
        }
        backing: dict[str, object] = {key: malformed}
        generated = False

        def generate() -> bytes:
            nonlocal generated
            generated = True
            return PRIVACY_KEY

        with fake_home_assistant_storage():
            module = load_adapter()
            caches = module.HomeAssistantProviderCaches(
                FakeHomeAssistant(backing), "entry-a", generate_privacy_key=generate
            )
            with self.assertRaisesRegex(
                ValueError, "unsupported provider cache schema"
            ):
                asyncio.run(
                    caches.async_initialize(
                        evaluated_at=NOW,
                        maximum_geocode_age=timedelta(hours=2),
                        maximum_route_age=timedelta(hours=3),
                    )
                )

        self.assertFalse(generated)
        self.assertEqual(backing[key], malformed)
        self.assertEqual(FakeStore.instances[0].save_calls, 0)


if __name__ == "__main__":
    unittest.main()
