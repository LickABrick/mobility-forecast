from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, ClassVar

from custom_components.mobility_forecast.storage import (
    STORAGE_SCHEMA_VERSION,
    ProfileState,
    encode_profile_state,
    profile_storage_key,
)
from tests.test_storage import state

ADAPTER_MODULE = "custom_components.mobility_forecast.ha_storage"


class FakeHomeAssistant:
    def __init__(self, backing: dict[str, object] | None = None) -> None:
        self.storage_backing = backing if backing is not None else {}


class FakeStore:
    instances: ClassVar[list[FakeStore]] = []

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
        self.remove_calls = 0
        self.__class__.instances.append(self)

    @classmethod
    def __class_getitem__(cls, item: object) -> type[FakeStore]:
        del item
        return cls

    async def async_load(self) -> object | None:
        value = self.hass.storage_backing.get(self.key)
        return None if value is None else json.loads(json.dumps(value))

    async def async_save(self, data: object) -> None:
        self.hass.storage_backing[self.key] = json.loads(json.dumps(data))

    async def async_remove(self) -> None:
        self.remove_calls += 1
        self.hass.storage_backing.pop(self.key, None)


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


class HomeAssistantProfileStorageTests(unittest.TestCase):
    def test_missing_store_loads_explicit_empty_profile_state(self) -> None:
        hass = FakeHomeAssistant()

        with fake_home_assistant_storage():
            adapter_module = load_adapter()
            adapter = adapter_module.HomeAssistantProfileStorage(hass, "entry-a")
            restored = asyncio.run(adapter.load("entry-a"))

        self.assertEqual(restored, ProfileState((), (), ()))
        store = FakeStore.instances[0]
        self.assertEqual(store.version, STORAGE_SCHEMA_VERSION)
        self.assertEqual(store.key, profile_storage_key("entry-a"))
        self.assertTrue(store.private)
        self.assertTrue(store.atomic_writes)

    def test_entries_are_isolated_and_reject_cross_entry_access(self) -> None:
        hass = FakeHomeAssistant()
        first_state = state()
        second_state = ProfileState((), (), ())

        with fake_home_assistant_storage():
            adapter_module = load_adapter()
            first = adapter_module.HomeAssistantProfileStorage(hass, "entry-a")
            second = adapter_module.HomeAssistantProfileStorage(hass, "entry-b")
            asyncio.run(first.save("entry-a", first_state))
            asyncio.run(second.save("entry-b", second_state))

            self.assertEqual(asyncio.run(first.load("entry-a")), first_state)
            self.assertEqual(asyncio.run(second.load("entry-b")), second_state)
            with self.assertRaisesRegex(ValueError, "config entry mismatch"):
                asyncio.run(first.load("entry-b"))
            with self.assertRaisesRegex(ValueError, "config entry mismatch"):
                asyncio.run(first.save("entry-b", first_state))

        self.assertEqual(
            set(hass.storage_backing),
            {profile_storage_key("entry-a"), profile_storage_key("entry-b")},
        )

    def test_restart_restores_state_without_reusing_runtime_objects(self) -> None:
        backing: dict[str, object] = {}
        original = state()

        with fake_home_assistant_storage():
            adapter_module = load_adapter()
            before_restart = adapter_module.HomeAssistantProfileStorage(
                FakeHomeAssistant(backing), "entry-a"
            )
            asyncio.run(before_restart.save("entry-a", original))

            after_restart = adapter_module.HomeAssistantProfileStorage(
                FakeHomeAssistant(backing), "entry-a"
            )
            restored = asyncio.run(after_restart.load("entry-a"))

        self.assertEqual(restored, original)
        self.assertIsNot(before_restart, after_restart)
        self.assertEqual(len(FakeStore.instances), 2)

    def test_malformed_payload_fails_closed_without_overwriting_store(self) -> None:
        key = profile_storage_key("entry-a")
        malformed = {**encode_profile_state(state()), "version": 99}
        backing: dict[str, object] = {key: malformed}

        with fake_home_assistant_storage():
            adapter_module = load_adapter()
            adapter = adapter_module.HomeAssistantProfileStorage(
                FakeHomeAssistant(backing), "entry-a"
            )
            with self.assertRaisesRegex(ValueError, "unsupported storage schema"):
                asyncio.run(adapter.load("entry-a"))

        self.assertEqual(backing[key], malformed)
        self.assertEqual(FakeStore.instances[0].remove_calls, 0)


if __name__ == "__main__":
    unittest.main()
