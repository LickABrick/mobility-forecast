from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, ClassVar

from tests.synthetic_pipeline import SyntheticCalendarEvent
from tests.test_ha_http_sender import SyntheticResponse, SyntheticSession

INTEGRATION_MODULE = "custom_components.mobility_forecast"


class FakePlatform(StrEnum):
    SENSOR = "sensor"


class FakeConfigEntry:
    def __init__(
        self,
        entry_id: str,
        *,
        data: dict[str, object] | None = None,
        version: int = 1,
        minor_version: int = 6,
    ) -> None:
        self.entry_id = entry_id
        self.data = (
            {
                "calendar_entity_ids": ["calendar.synthetic"],
                "start_anchor_entity_id": "zone.synthetic_start",
                "end_anchor_entity_id": "zone.synthetic_end",
                "physical_event_policy": "include",
                "online_event_policy": "exclude",
                "all_day_event_policy": "exclude",
                "no_location_event_policy": "exclude",
                "route_provider": "openrouteservice_hosted",
                "route_provider_api_key": "synthetic-test-key",
                "location_data_consent": "accepted",
                "max_geocode_requests_per_refresh": 8,
                "max_route_requests_per_refresh": 16,
                "max_request_attempts": 2,
                "request_timeout_seconds": 10,
                "geocode_cache_retention_hours": 72,
                "route_cache_fresh_hours": 6,
                "route_cache_stale_hours": 24,
                "toll_policy": "avoid",
                "highway_policy": "allow",
                "minimum_history_samples": 5,
                "minimum_correction_percent": 60,
                "maximum_correction_percent": 180,
                "cold_start_p90_percent": 125,
            }
            if data is None
            else data
        )
        self.version = version
        self.minor_version = minor_version
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
        self.updated: list[tuple[FakeConfigEntry, dict[str, object]]] = []

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

    def async_update_entry(self, entry: FakeConfigEntry, **changes: object) -> None:
        self.updated.append((entry, changes))
        if "data" in changes:
            entry.data = changes["data"]  # type: ignore[assignment]
        if "minor_version" in changes:
            entry.minor_version = changes["minor_version"]  # type: ignore[assignment]


class FakeHomeAssistant:
    def __init__(self, manager: FakeConfigEntriesManager) -> None:
        self.config_entries = manager
        self.storage_backing: dict[str, object] = {}
        self.data: dict[str, object] = {
            "calendar": FakeCalendarComponent(FakeCalendarEntity())
        }
        self.states = FakeStates(
            {
                "zone.synthetic_start": FakeState(
                    {"latitude": 12.5, "longitude": -34.25}
                ),
                "zone.synthetic_end": FakeState({"latitude": -20.0, "longitude": 40.0}),
            }
        )
        self.intervals: list[tuple[object, object]] = []
        self.cancelled_intervals = 0
        self.http_session: object = object()


class FakeState:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = attributes


class FakeStates:
    def __init__(self, states: dict[str, FakeState]) -> None:
        self.states = states
        self.lookups: list[str] = []

    def get(self, entity_id: str) -> FakeState | None:
        self.lookups.append(entity_id)
        return self.states.get(entity_id)


class FakeCalendarEntity:
    def __init__(self, events: list[object] | None = None) -> None:
        self.calls: list[tuple[object, datetime, datetime]] = []
        self.events = events if events is not None else []

    async def async_get_events(
        self, hass: object, start_date: datetime, end_date: datetime
    ) -> list[object]:
        self.calls.append((hass, start_date, end_date))
        return self.events


class FakeCalendarComponent:
    def __init__(self, entity: FakeCalendarEntity) -> None:
        self.entity = entity

    def get_entity(self, entity_id: str) -> FakeCalendarEntity | None:
        return self.entity if entity_id == "calendar.synthetic" else None


class SequencedSyntheticSession(SyntheticSession):
    def __init__(self, responses: list[SyntheticResponse]) -> None:
        super().__init__()
        self.responses = responses

    def request(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.response = self.responses.pop(0)
        return super().request(*args, **kwargs)  # type: ignore[arg-type]


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
        self.load_calls = 0
        self.remove_calls = 0
        self.__class__.instances.append(self)

    @classmethod
    def __class_getitem__(cls, item: object) -> type[FakeStore]:
        del item
        return cls

    async def async_load(self) -> object | None:
        self.load_calls += 1
        return self.hass.storage_backing.get(self.key)

    async def async_save(self, data: object) -> None:
        self.hass.storage_backing[self.key] = data

    async def async_remove(self) -> None:
        self.remove_calls += 1
        self.hass.storage_backing.pop(self.key, None)


@contextmanager
def fake_home_assistant() -> Generator[None]:
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    calendar = types.ModuleType("homeassistant.components.calendar")
    calendar_const = types.ModuleType("homeassistant.components.calendar.const")
    calendar_const.DATA_COMPONENT = "calendar"  # type: ignore[attr-defined]
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = FakeConfigEntry  # type: ignore[attr-defined]
    const = types.ModuleType("homeassistant.const")
    const.Platform = FakePlatform  # type: ignore[attr-defined]
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = FakeHomeAssistant  # type: ignore[attr-defined]
    helpers = types.ModuleType("homeassistant.helpers")
    event = types.ModuleType("homeassistant.helpers.event")

    def async_track_time_interval(
        hass: FakeHomeAssistant, callback: object, interval: object
    ) -> object:
        hass.intervals.append((callback, interval))

        def cancel() -> None:
            hass.cancelled_intervals += 1

        return cancel

    event.async_track_time_interval = async_track_time_interval  # type: ignore[attr-defined]
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass.http_session  # type: ignore[attr-defined]
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = FakeStore  # type: ignore[attr-defined]
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.now = lambda: datetime(2032, 4, 5, 7, 0, tzinfo=UTC)  # type: ignore[attr-defined]
    util.dt = dt  # type: ignore[attr-defined]

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.calendar": calendar,
        "homeassistant.components.calendar.const": calendar_const,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.event": event,
        "homeassistant.helpers.aiohttp_client": aiohttp_client,
        "homeassistant.helpers.storage": storage,
        "homeassistant.util": util,
        "homeassistant.util.dt": dt,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    FakeStore.instances.clear()
    try:
        yield
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
        sys.modules.pop(INTEGRATION_MODULE, None)
        sys.modules.pop("custom_components.mobility_forecast.ha_storage", None)


def load_integration() -> Any:
    return importlib.import_module(INTEGRATION_MODULE)


class ConfigEntryLifecycleTests(unittest.TestCase):
    def test_migrates_legacy_empty_entry_to_explicit_unconfigured_marker(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry("entry-a", data={}, minor_version=1)

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(
            manager.updated,
            [
                (
                    entry,
                    {
                        "data": {"calendar_entity_ids": []},
                        "minor_version": 6,
                    },
                )
            ],
        )
        self.assertEqual(entry.data, {"calendar_entity_ids": []})

    def test_migrates_calendar_entry_without_guessing_planning_policy(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry(
            "entry-a",
            data={"calendar_entity_ids": ["calendar.synthetic"]},
            minor_version=2,
        )

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(
            manager.updated,
            [
                (
                    entry,
                    {
                        "data": {"calendar_entity_ids": ["calendar.synthetic"]},
                        "minor_version": 6,
                    },
                )
            ],
        )
        self.assertNotIn("start_anchor_entity_id", entry.data)

    def test_migrates_planning_entry_without_guessing_route_provider(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        data: dict[str, object] = {
            "calendar_entity_ids": ["calendar.synthetic"],
            "start_anchor_entity_id": "zone.synthetic_start",
            "end_anchor_entity_id": "zone.synthetic_end",
            "physical_event_policy": "include",
            "online_event_policy": "exclude",
            "all_day_event_policy": "exclude",
            "no_location_event_policy": "exclude",
        }
        entry = FakeConfigEntry("entry-a", data=data, minor_version=3)

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(entry.minor_version, 6)
        self.assertEqual(entry.data, data)
        self.assertNotIn("route_provider", entry.data)
        self.assertNotIn("route_provider_api_key", entry.data)

    def test_migrates_google_only_entry_without_guessing_replacement_provider(
        self,
    ) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        data: dict[str, object] = {
            "calendar_entity_ids": ["calendar.synthetic"],
            "start_anchor_entity_id": "zone.synthetic_start",
            "end_anchor_entity_id": "zone.synthetic_end",
            "physical_event_policy": "include",
            "online_event_policy": "exclude",
            "all_day_event_policy": "exclude",
            "no_location_event_policy": "exclude",
            "route_provider": "google_routes",
            "route_provider_api_key": "synthetic-legacy-key",
            "toll_policy": "avoid",
            "highway_policy": "allow",
        }
        entry = FakeConfigEntry("entry-a", data=data, minor_version=4)

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(entry.minor_version, 6)
        self.assertNotIn("route_provider", entry.data)
        self.assertNotIn("route_provider_api_key", entry.data)
        self.assertEqual(entry.data["toll_policy"], "avoid")
        self.assertEqual(entry.data["highway_policy"], "allow")
        self.assertNotIn("location_data_consent", entry.data)
        self.assertNotIn("routing_base_url", entry.data)

    def test_migrates_route_entry_without_guessing_forecast_policy(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        data = dict(FakeConfigEntry("template").data)
        for key in (
            "minimum_history_samples",
            "minimum_correction_percent",
            "maximum_correction_percent",
            "cold_start_p90_percent",
        ):
            data.pop(key)
        entry = FakeConfigEntry("entry-a", data=data, minor_version=5)

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(entry.minor_version, 6)
        self.assertEqual(entry.data, data)
        self.assertNotIn("minimum_history_samples", entry.data)

    def test_rejects_unknown_config_entry_major_version(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry("entry-a", version=2, minor_version=1)

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_migrate_entry(hass, entry))

        self.assertFalse(result)
        self.assertEqual(manager.updated, [])

    def test_migration_never_overwrites_current_or_unknown_legacy_data(self) -> None:
        cases = (
            FakeConfigEntry(
                "entry-current",
                data={"calendar_entity_ids": ["calendar.synthetic"]},
                minor_version=6,
            ),
            FakeConfigEntry(
                "entry-legacy-data",
                data={"unexpected": "synthetic"},
                minor_version=1,
            ),
        )

        for entry in cases:
            with self.subTest(entry_id=entry.entry_id):
                manager = FakeConfigEntriesManager()
                hass = FakeHomeAssistant(manager)
                original_data = dict(entry.data)

                with fake_home_assistant():
                    integration = load_integration()
                    result = asyncio.run(integration.async_migrate_entry(hass, entry))

                self.assertEqual(result, entry.minor_version == 6)
                self.assertEqual(entry.data, original_data)
                self.assertEqual(manager.updated, [])

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
        self.assertIsNotNone(first.runtime_data.coordinator.data)  # type: ignore[union-attr]
        self.assertTrue(first.runtime_data.coordinator.last_update_success)  # type: ignore[union-attr]
        self.assertEqual(len(hass.intervals), 2)
        self.assertEqual(
            hass.states.lookups,
            [
                "zone.synthetic_start",
                "zone.synthetic_end",
                "zone.synthetic_start",
                "zone.synthetic_end",
            ],
        )
        self.assertTrue(
            all(
                interval == timedelta(minutes=15)
                for _callback, interval in hass.intervals
            )
        )

    def test_missing_selected_zone_keeps_latest_runtime_update_unavailable(
        self,
    ) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        hass.states.states.pop("zone.synthetic_end")
        entry = FakeConfigEntry("entry-a")

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_setup_entry(hass, entry))

        self.assertTrue(result)
        self.assertIsNotNone(entry.runtime_data)
        self.assertFalse(entry.runtime_data.coordinator.last_update_success)  # type: ignore[union-attr]
        self.assertIsNone(entry.runtime_data.coordinator.data)  # type: ignore[union-attr]
        calendar = hass.data["calendar"]
        self.assertEqual(calendar.entity.calls, [])  # type: ignore[union-attr]

    def test_successful_unload_clears_runtime_after_platform_unload(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        entry = FakeConfigEntry("entry-a")

        with fake_home_assistant():
            integration = load_integration()
            asyncio.run(integration.async_setup_entry(hass, entry))
            runtime = entry.runtime_data
            self.assertTrue(runtime.coordinator.last_update_success)  # type: ignore[union-attr]
            result = asyncio.run(integration.async_unload_entry(hass, entry))

        self.assertTrue(result)
        self.assertEqual(manager.unloaded, [(entry, (FakePlatform.SENSOR,))])
        self.assertIsNotNone(runtime)
        self.assertIsNone(entry.runtime_data)
        self.assertEqual(len(FakeStore.instances), 2)
        self.assertEqual([store.load_calls for store in FakeStore.instances], [1, 1])
        self.assertTrue(all(store.remove_calls == 0 for store in FakeStore.instances))
        self.assertEqual(hass.cancelled_intervals, 1)

    def test_runtime_composes_real_http_pipeline_into_nonzero_forecast(self) -> None:
        manager = FakeConfigEntriesManager()
        hass = FakeHomeAssistant(manager)
        hass.data["calendar"].entity.events = [  # type: ignore[union-attr]
            SyntheticCalendarEvent(
                start=datetime(2032, 4, 5, 9, 0, tzinfo=UTC),
                end=datetime(2032, 4, 5, 10, 0, tzinfo=UTC),
                summary="Synthetic appointment",
                location="Synthetic destination",
                uid="synthetic-event",
            )
        ]
        hass.http_session = SequencedSyntheticSession(
            [
                SyntheticResponse(
                    200,
                    b'{"features":[{"geometry":{"type":"Point","coordinates":[-33,13]}}]}',
                ),
                SyntheticResponse(
                    200,
                    b'{"routes":[{"summary":{"distance":10000,"duration":900}}]}',
                ),
            ]
        )
        entry = FakeConfigEntry("entry-routed")

        with fake_home_assistant():
            integration = load_integration()
            result = asyncio.run(integration.async_setup_entry(hass, entry))

        self.assertTrue(result)
        snapshot = entry.runtime_data.coordinator.data  # type: ignore[union-attr]
        self.assertEqual(snapshot.forecasts[0].distance_p50_m, 10_000)
        self.assertEqual(snapshot.forecasts[0].distance_p90_m, 12_500)
        self.assertEqual(len(hass.http_session.calls), 2)  # type: ignore[attr-defined]

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
