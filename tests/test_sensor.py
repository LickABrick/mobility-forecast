from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
import unittest
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from custom_components.mobility_forecast.coordinator import (
    CoordinatorSnapshot,
    ProfileCoordinator,
)
from custom_components.mobility_forecast.domain import DataQuality, Forecast

NOW = datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
INTEGRATION = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "mobility_forecast"
)
SENSOR_MODULE = "custom_components.mobility_forecast.sensor"


class FakeSensorEntity:
    pass


class FakeUnitOfLength:
    KILOMETERS = "km"


@contextmanager
def fake_home_assistant() -> Generator[None]:
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    sensor = types.ModuleType("homeassistant.components.sensor")
    sensor.SensorEntity = FakeSensorEntity  # type: ignore[attr-defined]
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object  # type: ignore[attr-defined]
    const = types.ModuleType("homeassistant.const")
    const.UnitOfLength = FakeUnitOfLength  # type: ignore[attr-defined]
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object  # type: ignore[attr-defined]
    helpers = types.ModuleType("homeassistant.helpers")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddConfigEntryEntitiesCallback = (  # type: ignore[attr-defined]
        Callable[[list[object]], None]
    )

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.sensor": sensor,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.entity_platform": entity_platform,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        sys.modules.pop("custom_components.mobility_forecast.sensor", None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def forecast(
    service_date: date = date(2026, 1, 16),
    *,
    p50_m: int | None = 10_000,
    p90_m: int | None = 12_500,
    quality: DataQuality = DataQuality.PARTIAL,
) -> Forecast:
    return Forecast(
        service_date=service_date,
        distance_p50_m=p50_m,
        distance_p90_m=p90_m,
        required_soc_p50_percent=None,
        required_soc_p90_percent=None,
        quality=quality,
        reason_codes=("cold_start",),
    )


def coordinator_with(snapshot: CoordinatorSnapshot | None) -> ProfileCoordinator:
    coordinator = object.__new__(ProfileCoordinator)
    coordinator._data = snapshot  # type: ignore[attr-defined]
    return coordinator


class FakeConfigEntry:
    def __init__(self, entry_id: str, runtime_data: object) -> None:
        self.entry_id = entry_id
        self.runtime_data = runtime_data


class ForecastDistanceSensorTests(unittest.TestCase):
    def test_sensor_projects_first_forecast_without_private_identifiers(self) -> None:
        snapshot = CoordinatorSnapshot(
            forecasts=(
                forecast(),
                forecast(date(2026, 1, 17), p50_m=20_000, p90_m=25_000),
            ),
            generated_at=NOW,
        )

        with fake_home_assistant():
            module = importlib.import_module(SENSOR_MODULE)
            entity = module.ForecastDistanceSensor(
                "entry-synthetic", coordinator_with(snapshot)
            )

        self.assertEqual(entity.unique_id, "entry-synthetic_forecast_distance")
        self.assertEqual(entity.translation_key, "forecast_distance")
        self.assertEqual(entity.native_unit_of_measurement, "km")
        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, 12.5)
        self.assertEqual(
            entity.extra_state_attributes,
            {
                "service_date": "2026-01-16",
                "distance_p50_km": 10.0,
                "quality": "partial",
                "generated_at": NOW.isoformat(),
            },
        )
        serialized = repr(entity.extra_state_attributes)
        self.assertNotIn("entry-synthetic", serialized)
        self.assertNotIn("event", serialized)
        self.assertNotIn("coordinates", serialized)

    def test_sensor_is_unavailable_until_a_snapshot_exists(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(SENSOR_MODULE)
            entity = module.ForecastDistanceSensor(
                "entry-synthetic", coordinator_with(None)
            )

        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)
        self.assertEqual(entity.extra_state_attributes, {})

    def test_unavailable_forecast_remains_explicit_not_zero_distance(self) -> None:
        snapshot = CoordinatorSnapshot(
            forecasts=(
                forecast(
                    p50_m=None,
                    p90_m=None,
                    quality=DataQuality.UNAVAILABLE,
                ),
            ),
            generated_at=NOW,
        )

        with fake_home_assistant():
            module = importlib.import_module(SENSOR_MODULE)
            entity = module.ForecastDistanceSensor(
                "entry-synthetic", coordinator_with(snapshot)
            )

        self.assertTrue(entity.available)
        self.assertIsNone(entity.native_value)
        self.assertIsNone(entity.extra_state_attributes["distance_p50_km"])
        self.assertEqual(entity.extra_state_attributes["quality"], "unavailable")

    def test_entity_name_has_matching_source_and_english_translation(self) -> None:
        strings = json.loads((INTEGRATION / "strings.json").read_text())
        english = json.loads((INTEGRATION / "translations" / "en.json").read_text())

        self.assertEqual(english, strings)
        self.assertEqual(
            strings["entity"]["sensor"]["forecast_distance"],
            {"name": "Forecast distance"},
        )

    def test_platform_adds_exactly_one_entry_scoped_read_only_entity(self) -> None:
        snapshot = CoordinatorSnapshot((forecast(),), NOW)
        entry = FakeConfigEntry("entry-synthetic", coordinator_with(snapshot))
        added: list[Any] = []

        with fake_home_assistant():
            module = importlib.import_module(SENSOR_MODULE)
            asyncio.run(module.async_setup_entry(object(), entry, added.extend))

        self.assertEqual(len(added), 1)
        self.assertIsInstance(added[0], FakeSensorEntity)
        self.assertEqual(added[0].unique_id, "entry-synthetic_forecast_distance")
        self.assertNotIn("async_turn_on", module.ForecastDistanceSensor.__dict__)
        self.assertNotIn("async_update", module.ForecastDistanceSensor.__dict__)


if __name__ == "__main__":
    unittest.main()
