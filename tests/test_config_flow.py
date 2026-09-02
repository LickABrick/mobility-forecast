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


class FakeAll:
    def __init__(self, *validators: object) -> None:
        self.validators = validators


class FakeInvalid(Exception):
    pass


class FakeEntitySelectorConfig:
    def __init__(self, *, domain: str, multiple: bool) -> None:
        self.domain = domain
        self.multiple = multiple


class FakeEntitySelector:
    def __init__(self, config: FakeEntitySelectorConfig) -> None:
        self.config = config


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
    helpers = types.ModuleType("homeassistant.helpers")
    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.EntitySelector = FakeEntitySelector  # type: ignore[attr-defined]
    selector.EntitySelectorConfig = FakeEntitySelectorConfig  # type: ignore[attr-defined]
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.All = FakeAll  # type: ignore[attr-defined]
    voluptuous.Invalid = FakeInvalid  # type: ignore[attr-defined]
    voluptuous.Required = lambda key: key  # type: ignore[attr-defined]
    voluptuous.Schema = FakeSchema  # type: ignore[attr-defined]

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.selector": selector,
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
        self.assertEqual(
            manifest["issue_tracker"],
            "https://github.com/LickABrick/mobility-forecast/issues",
        )
        self.assertEqual(manifest["iot_class"], "local_polling")
        self.assertEqual(manifest["codeowners"], [])
        self.assertEqual(manifest["dependencies"], ["calendar"])
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(
            manifest["documentation"],
            "https://github.com/LickABrick/mobility-forecast",
        )
        self.assertEqual(hacs, {"name": "Mobility Forecast"})

    def test_strings_and_translations_cover_profile_inputs(self) -> None:
        strings = json.loads((INTEGRATION / "strings.json").read_text())
        english = json.loads((INTEGRATION / "translations" / "en.json").read_text())

        self.assertEqual(english, strings)
        user_step = strings["config"]["step"]["user"]
        self.assertEqual(set(user_step["data"]), {"name", "calendar_entity_ids"})
        self.assertEqual(
            set(user_step["data_description"]),
            {"name", "calendar_entity_ids"},
        )
        self.assertEqual(
            strings["config"]["error"]["calendar_required"],
            "Select at least one calendar.",
        )


class ConfigFlowTests(unittest.TestCase):
    def test_user_step_creates_independent_calendar_profile_entries(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            flow_type = module.MobilityForecastConfigFlow
            self.assertEqual(flow_type.registered_domain, "mobility_forecast")
            self.assertEqual((flow_type.VERSION, flow_type.MINOR_VERSION), (1, 2))

            first = asyncio.run(
                flow_type().async_step_user(
                    {
                        "name": "Commuting",
                        "calendar_entity_ids": ["calendar.synthetic_work"],
                    }
                )
            )
            second = asyncio.run(
                flow_type().async_step_user(
                    {
                        "name": "Family",
                        "calendar_entity_ids": ["calendar.synthetic_family"],
                    }
                )
            )

        self.assertEqual(
            first,
            {
                "type": "create_entry",
                "title": "Commuting",
                "data": {"calendar_entity_ids": ["calendar.synthetic_work"]},
            },
        )
        self.assertEqual(
            second,
            {
                "type": "create_entry",
                "title": "Family",
                "data": {"calendar_entity_ids": ["calendar.synthetic_family"]},
            },
        )
        self.assertIsNot(first["data"], second["data"])

    def test_user_form_requires_name_and_calendar_without_defaults(self) -> None:
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
        self.assertEqual(set(schema.schema), {"name", "calendar_entity_ids"})
        self.assertIs(schema.schema["name"], str)
        calendar_validator = schema.schema["calendar_entity_ids"]
        self.assertIsInstance(calendar_validator, FakeEntitySelector)
        self.assertEqual(calendar_validator.config.domain, "calendar")
        self.assertIs(calendar_validator.config.multiple, True)

    def test_empty_calendar_selection_returns_serializable_form_error(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            result = asyncio.run(
                module.MobilityForecastConfigFlow().async_step_user(
                    {"name": "Empty", "calendar_entity_ids": []}
                )
            )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(result["errors"], {"calendar_entity_ids": "calendar_required"})


if __name__ == "__main__":
    unittest.main()
