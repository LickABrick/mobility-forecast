from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from enum import StrEnum
from typing import Any

INTEGRATION_MODULE = "custom_components.mobility_forecast"


class FakePlatform(StrEnum):
    SENSOR = "sensor"


class FakeConfigEntry:
    def __init__(self, entry_id: str) -> None:
        self.entry_id = entry_id
        self.runtime_data: object | None = None

    @classmethod
    def __class_getitem__(cls, item: object) -> type[FakeConfigEntry]:
        del item
        return cls


class FakeConfigEntriesManager:
    def __init__(
        self, *, unload_result: bool = True, forward_error: Exception | None = None
    ) -> None:
        self.unload_result = unload_result
        self.forward_error = forward_error
        self.forwarded: list[tuple[FakeConfigEntry, tuple[FakePlatform, ...]]] = []
        self.unloaded: list[tuple[FakeConfigEntry, tuple[FakePlatform, ...]]] = []

    async def async_forward_entry_setups(
        self, entry: FakeConfigEntry, platforms: tuple[FakePlatform, ...]
    ) -> None:
        self.forwarded.append((entry, platforms))
        if self.forward_error is not None:
            raise self.forward_error

    async def async_unload_platforms(
        self, entry: FakeConfigEntry, platforms: tuple[FakePlatform, ...]
    ) -> bool:
        self.unloaded.append((entry, platforms))
        return self.unload_result


class FakeHomeAssistant:
    def __init__(self, manager: FakeConfigEntriesManager) -> None:
        self.config_entries = manager


@contextmanager
def fake_home_assistant() -> Generator[None]:
    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = FakeConfigEntry  # type: ignore[attr-defined]
    const = types.ModuleType("homeassistant.const")
    const.Platform = FakePlatform  # type: ignore[attr-defined]
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = FakeHomeAssistant  # type: ignore[attr-defined]

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
        sys.modules.pop(INTEGRATION_MODULE, None)


def load_integration() -> Any:
    return importlib.import_module(INTEGRATION_MODULE)


class ConfigEntryLifecycleTests(unittest.TestCase):
    def test_setup_builds_isolated_runtime_and_forwards_sensor_platform(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        first = FakeConfigEntry("entry-a")
        second = FakeConfigEntry("entry-b")

        with fake_home_assistant():
            integration = load_integration()
            first_result = asyncio.run(integration.async_setup_entry(hass, first))
            second_result = asyncio.run(integration.async_setup_entry(hass, second))

        self.assertTrue(first_result)
        self.assertTrue(second_result)
        self.assertEqual(integration.PLATFORMS, (FakePlatform.SENSOR,))
        self.assertEqual(
            manager.forwarded,
            [
                (first, (FakePlatform.SENSOR,)),
                (second, (FakePlatform.SENSOR,)),
            ],
        )
        self.assertIsNotNone(first.runtime_data)
        self.assertIsNotNone(second.runtime_data)
        self.assertIsNot(first.runtime_data, second.runtime_data)
        self.assertIsNot(
            first.runtime_data.coordinator,  # type: ignore[union-attr]
            second.runtime_data.coordinator,  # type: ignore[union-attr]
        )
        self.assertIsNone(first.runtime_data.coordinator.data)  # type: ignore[union-attr]

    def test_successful_unload_clears_runtime_after_platform_unload(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry("entry-a")

        with fake_home_assistant():
            integration = load_integration()
            asyncio.run(integration.async_setup_entry(hass, entry))
            runtime = entry.runtime_data
            result = asyncio.run(integration.async_unload_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(manager.unloaded, [(entry, (FakePlatform.SENSOR,))])
        self.assertIsNotNone(runtime)
        self.assertIsNone(entry.runtime_data)

    def test_failed_platform_forwarding_releases_unloaded_runtime(self) -> None:
        manager = FakeConfigEntriesManager(
            forward_error=RuntimeError("synthetic forwarding failure")
        )
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry("entry-a")

        with fake_home_assistant():
            integration = load_integration()
            with self.assertRaisesRegex(RuntimeError, "synthetic forwarding failure"):
                asyncio.run(integration.async_setup_entry(hass, entry))

        self.assertEqual(manager.forwarded, [(entry, (FakePlatform.SENSOR,))])
        self.assertIsNone(entry.runtime_data)

    def test_failed_platform_unload_preserves_runtime_for_loaded_entities(self) -> None:
        manager = FakeConfigEntriesManager(unload_result=False)
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry("entry-a")

        with fake_home_assistant():
            integration = load_integration()
            asyncio.run(integration.async_setup_entry(hass, entry))
            runtime = entry.runtime_data
            result = asyncio.run(integration.async_unload_entry(hass, entry))

        self.assertFalse(result)
        self.assertIs(entry.runtime_data, runtime)


if __name__ == "__main__":
    unittest.main()
