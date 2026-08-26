from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "mobility_forecast"


class FakeSchema:
    def __init__(self, schema: dict[object, object]) -> None:
        self.schema = schema


class FakeConfigFlow:
    VERSION: int
    MINOR_VERSION: int
    registered_domain: str

    def __init_subclass__(cls, *, domain: str, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.registered_domain = domain

    def async_show_form(self, **kwargs: object) -> dict[str, object]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: object) -> dict[str, object]:
        return {"type": "create_entry", **kwargs}


@contextmanager
def fake_home_assistant() -> Generator[None]:
    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = FakeConfigFlow  # type: ignore[attr-defined]
    config_entries.ConfigFlowResult = dict[str, Any]  # type: ignore[attr-defined]
    const = types.ModuleType("homeassistant.const")
    const.CONF_NAME = "name"  # type: ignore[attr-defined]
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Required = lambda key: key  # type: ignore[attr-defined]
    voluptuous.Schema = FakeSchema  # type: ignore[attr-defined]

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "voluptuous": voluptuous,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        sys.modules.pop("custom_components.mobility_forecast.config_flow", None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


class IntegrationMetadataTests(unittest.TestCase):
    def test_manifest_and_hacs_metadata_declare_config_flow(self) -> None:
        manifest = json.loads((INTEGRATION / "manifest.json").read_text())
        hacs = json.loads((ROOT / "hacs.json").read_text())

        self.assertEqual(manifest["domain"], "mobility_forecast")
        self.assertEqual(manifest["name"], "Mobility Forecast")
        self.assertEqual(manifest["version"], "0.0.0")
        self.assertIs(manifest["config_flow"], True)
        self.assertEqual(manifest["integration_type"], "service")
        self.assertEqual(hacs, {"name": "Mobility Forecast"})
        self.assertNotIn("requirements", manifest)
        self.assertNotIn("documentation", manifest)
        self.assertNotIn("issue_tracker", manifest)

    def test_strings_and_translations_cover_the_only_input(self) -> None:
        strings = json.loads((INTEGRATION / "strings.json").read_text())
        english = json.loads((INTEGRATION / "translations" / "en.json").read_text())

        self.assertEqual(english, strings)
        user_step = strings["config"]["step"]["user"]
        self.assertEqual(set(user_step["data"]), {"name"})
        self.assertNotIn("data_description", user_step)


class ConfigFlowTests(unittest.TestCase):
    def test_user_step_creates_independent_empty_profile_entries(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            flow_type = module.MobilityForecastConfigFlow
            self.assertEqual(flow_type.registered_domain, "mobility_forecast")
            self.assertEqual((flow_type.VERSION, flow_type.MINOR_VERSION), (1, 1))

            first = asyncio.run(flow_type().async_step_user({"name": "Commuting"}))
            second = asyncio.run(flow_type().async_step_user({"name": "Family"}))

        self.assertEqual(
            first,
            {"type": "create_entry", "title": "Commuting", "data": {}},
        )
        self.assertEqual(
            second,
            {"type": "create_entry", "title": "Family", "data": {}},
        )
        self.assertIsNot(first["data"], second["data"])

    def test_user_form_has_required_name_without_a_default(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            result = asyncio.run(
                module.MobilityForecastConfigFlow().async_step_user(None)
            )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        schema = result["data_schema"]
        self.assertIsInstance(schema, FakeSchema)
        self.assertEqual(schema.schema, {"name": str})


if __name__ == "__main__":
    unittest.main()
