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
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "mobility_forecast"
POLICY_FIELDS = {
    "start_anchor_entity_id",
    "end_anchor_entity_id",
    "physical_event_policy",
    "online_event_policy",
    "all_day_event_policy",
    "no_location_event_policy",
}
ROUTE_FIELDS = {
    "route_provider",
    "route_provider_api_key",
    "routing_base_url",
    "geocoder_provider",
    "geocoder_base_url",
    "location_data_consent",
    "max_geocode_requests_per_refresh",
    "max_route_requests_per_refresh",
    "max_request_attempts",
    "request_timeout_seconds",
    "geocode_cache_retention_hours",
    "route_cache_fresh_hours",
    "route_cache_stale_hours",
    "toll_policy",
    "highway_policy",
}
CONFIG_FIELDS = POLICY_FIELDS | ROUTE_FIELDS
PROFILE_INPUT_FIELDS = {"name", "calendar_entity_ids", *CONFIG_FIELDS}
POLICY_INPUT = {
    "start_anchor_entity_id": "zone.synthetic_start",
    "end_anchor_entity_id": "zone.synthetic_end",
    "physical_event_policy": "include",
    "online_event_policy": "exclude",
    "all_day_event_policy": "exclude",
    "no_location_event_policy": "exclude",
}
ROUTE_INPUT = {
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
}
ENDPOINT_PLACEHOLDERS = {
    "ors_geocoding_endpoint": "https://api.openrouteservice.org/geocode/search",
    "ors_routing_endpoint": (
        "https://api.openrouteservice.org/v2/directions/driving-car"
    ),
    "geoapify_geocoding_endpoint": "https://api.geoapify.com/v1/geocode/search",
    "geoapify_routing_endpoint": "https://api.geoapify.com/v1/routing",
    "google_geocoding_endpoint": ("https://maps.googleapis.com/maps/api/geocode/json"),
    "google_routing_endpoint": (
        "https://routes.googleapis.com/directions/v2:computeRoutes"
    ),
}


class FakeSchema:
    def __init__(self, schema: dict[object, object]) -> None:
        self.schema = schema


class FakeAll:
    def __init__(self, *validators: object) -> None:
        self.validators = validators


class FakeIn:
    def __init__(self, container: object) -> None:
        self.container = container


class FakeInvalid(Exception):
    pass


class FakeEntitySelectorConfig:
    def __init__(self, *, domain: str, multiple: bool = False) -> None:
        self.domain = domain
        self.multiple = multiple


class FakeEntitySelector:
    def __init__(self, config: FakeEntitySelectorConfig) -> None:
        self.config = config


class FakeTextSelectorConfig:
    def __init__(self, *, type: str) -> None:
        self.type = type


class FakeTextSelector:
    def __init__(self, config: FakeTextSelectorConfig) -> None:
        self.config = config


class FakeTextSelectorType:
    PASSWORD = "password"
    URL = "url"


class FakeNumberSelectorConfig:
    def __init__(self, *, min: int, max: int, step: int, mode: str) -> None:
        self.min = min
        self.max = max
        self.step = step
        self.mode = mode


class FakeNumberSelector:
    def __init__(self, config: FakeNumberSelectorConfig) -> None:
        self.config = config


class FakeNumberSelectorMode:
    BOX = "box"


class FakeConfigFlow:
    VERSION: int
    MINOR_VERSION: int
    registered_domain: str
    reconfigure_entry: SimpleNamespace

    def __init_subclass__(cls, *, domain: str, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.registered_domain = domain

    def async_show_form(self, **kwargs: object) -> dict[str, object]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: object) -> dict[str, object]:
        return {"type": "create_entry", **kwargs}

    def _get_reconfigure_entry(self) -> SimpleNamespace:
        return self.reconfigure_entry

    def async_update_reload_and_abort(
        self,
        entry: SimpleNamespace,
        *,
        data: dict[str, object] | None = None,
        data_updates: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if data is not None and data_updates is not None:
            raise ValueError("data and data_updates are mutually exclusive")
        if data is not None:
            entry.data = dict(data)
        elif data_updates is not None:
            entry.data = {**entry.data, **data_updates}
        return {
            "type": "abort",
            "reason": "reconfigure_successful",
            "data": entry.data,
        }


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
    selector.NumberSelector = FakeNumberSelector  # type: ignore[attr-defined]
    selector.NumberSelectorConfig = FakeNumberSelectorConfig  # type: ignore[attr-defined]
    selector.NumberSelectorMode = FakeNumberSelectorMode  # type: ignore[attr-defined]
    selector.TextSelector = FakeTextSelector  # type: ignore[attr-defined]
    selector.TextSelectorConfig = FakeTextSelectorConfig  # type: ignore[attr-defined]
    selector.TextSelectorType = FakeTextSelectorType  # type: ignore[attr-defined]
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.All = FakeAll  # type: ignore[attr-defined]
    voluptuous.In = FakeIn  # type: ignore[attr-defined]
    voluptuous.Invalid = FakeInvalid  # type: ignore[attr-defined]
    voluptuous.Optional = lambda key: key  # type: ignore[attr-defined]
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
        for step_id, expected_fields in (
            ("user", PROFILE_INPUT_FIELDS),
            ("reconfigure", CONFIG_FIELDS),
        ):
            step = strings["config"]["step"][step_id]
            self.assertEqual(set(step["data"]), expected_fields)
            self.assertEqual(set(step["data_description"]), expected_fields)
        self.assertEqual(
            strings["config"]["error"]["calendar_required"],
            "Select at least one calendar.",
        )
        self.assertIn("invalid_planning_policy", strings["config"]["error"])
        self.assertIn("invalid_route_provider", strings["config"]["error"])
        self.assertIn("reconfigure_successful", strings["config"]["abort"])
        provider_description = strings["config"]["step"]["user"]["data_description"][
            "route_provider"
        ]
        self.assertNotIn("https://", provider_description)
        self.assertEqual(
            {
                "{ors_geocoding_endpoint}",
                "{ors_routing_endpoint}",
                "{geoapify_geocoding_endpoint}",
                "{geoapify_routing_endpoint}",
                "{google_geocoding_endpoint}",
                "{google_routing_endpoint}",
            },
            {
                placeholder
                for placeholder in (
                    "{ors_geocoding_endpoint}",
                    "{ors_routing_endpoint}",
                    "{geoapify_geocoding_endpoint}",
                    "{geoapify_routing_endpoint}",
                    "{google_geocoding_endpoint}",
                    "{google_routing_endpoint}",
                )
                if placeholder in provider_description
            },
        )


class ConfigFlowTests(unittest.TestCase):
    def test_user_step_creates_independent_explicit_profile_entries(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            flow_type = module.MobilityForecastConfigFlow
            self.assertEqual(flow_type.registered_domain, "mobility_forecast")
            self.assertEqual((flow_type.VERSION, flow_type.MINOR_VERSION), (1, 5))

            first = asyncio.run(
                flow_type().async_step_user(
                    {
                        "name": "Commuting",
                        "calendar_entity_ids": ["calendar.synthetic_work"],
                        **POLICY_INPUT,
                        **ROUTE_INPUT,
                    }
                )
            )
            second = asyncio.run(
                flow_type().async_step_user(
                    {
                        "name": "Family",
                        "calendar_entity_ids": ["calendar.synthetic_family"],
                        **{
                            **POLICY_INPUT,
                            **ROUTE_INPUT,
                            "start_anchor_entity_id": "zone.synthetic_family_start",
                        },
                    }
                )
            )

        self.assertEqual(first["type"], "create_entry")
        self.assertEqual(first["title"], "Commuting")
        self.assertEqual(
            first["data"],
            {
                "calendar_entity_ids": ["calendar.synthetic_work"],
                **POLICY_INPUT,
                **ROUTE_INPUT,
            },
        )
        self.assertEqual(second["type"], "create_entry")
        self.assertIsNot(first["data"], second["data"])

    def test_user_form_requires_every_profile_choice_without_defaults(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            result = asyncio.run(
                module.MobilityForecastConfigFlow().async_step_user(None)
            )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(result["description_placeholders"], ENDPOINT_PLACEHOLDERS)
        schema = result["data_schema"]
        self.assertIsInstance(schema, FakeSchema)
        self.assertEqual(set(schema.schema), PROFILE_INPUT_FIELDS)
        self.assertIs(schema.schema["name"], str)
        calendar_validator = schema.schema["calendar_entity_ids"]
        self.assertIsInstance(calendar_validator, FakeEntitySelector)
        self.assertEqual(calendar_validator.config.domain, "calendar")
        self.assertIs(calendar_validator.config.multiple, True)
        for field in ("start_anchor_entity_id", "end_anchor_entity_id"):
            validator = schema.schema[field]
            self.assertIsInstance(validator, FakeEntitySelector)
            self.assertEqual(validator.config.domain, "zone")
            self.assertIs(validator.config.multiple, False)
        for field in POLICY_FIELDS - {
            "start_anchor_entity_id",
            "end_anchor_entity_id",
        }:
            validator = schema.schema[field]
            self.assertIsInstance(validator, FakeIn)
            self.assertEqual(
                validator.container,
                {"include": "Include", "exclude": "Exclude"},
            )
        self.assertEqual(
            schema.schema["route_provider"].container,
            {
                "openrouteservice_hosted": "OpenRouteService hosted (recommended)",
                "openrouteservice_self_hosted": (
                    "Self-hosted OpenRouteService + separate geocoder"
                ),
                "geoapify": "Geoapify",
                "google": "Google Routes + Geocoding",
            },
        )
        self.assertEqual(
            schema.schema["geocoder_provider"].container,
            {"pelias": "Pelias", "photon": "Photon", "nominatim": "Nominatim"},
        )
        self.assertEqual(
            schema.schema["location_data_consent"].container,
            {"accepted": "I understand and consent"},
        )
        for field in ("toll_policy", "highway_policy"):
            self.assertEqual(
                schema.schema[field].container,
                {"allow": "Allow", "avoid": "Avoid"},
            )
        credential = schema.schema["route_provider_api_key"]
        self.assertIsInstance(credential, FakeTextSelector)
        self.assertEqual(credential.config.type, "password")
        for field in ("routing_base_url", "geocoder_base_url"):
            endpoint = schema.schema[field]
            self.assertIsInstance(endpoint, FakeTextSelector)
            self.assertEqual(endpoint.config.type, "url")
        expected_maxima = {
            "max_geocode_requests_per_refresh": 50,
            "max_route_requests_per_refresh": 100,
            "max_request_attempts": 3,
            "request_timeout_seconds": 30,
            "geocode_cache_retention_hours": 720,
            "route_cache_fresh_hours": 24,
            "route_cache_stale_hours": 720,
        }
        for field, maximum in expected_maxima.items():
            validator = schema.schema[field]
            self.assertIsInstance(validator, FakeNumberSelector)
            self.assertEqual(
                (validator.config.min, validator.config.max, validator.config.step),
                (1, maximum, 1),
            )
            self.assertEqual(validator.config.mode, "box")

    def test_empty_calendar_selection_returns_serializable_form_error(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            result = asyncio.run(
                module.MobilityForecastConfigFlow().async_step_user(
                    {
                        "name": "Empty",
                        "calendar_entity_ids": [],
                        **POLICY_INPUT,
                        **ROUTE_INPUT,
                    }
                )
            )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(result["errors"], {"calendar_entity_ids": "calendar_required"})

    def test_invalid_planning_policy_returns_privacy_safe_base_error(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            result = asyncio.run(
                module.MobilityForecastConfigFlow().async_step_user(
                    {
                        "name": "Invalid",
                        "calendar_entity_ids": ["calendar.synthetic"],
                        **{**POLICY_INPUT, "online_event_policy": "automatic"},
                        **ROUTE_INPUT,
                    }
                )
            )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "invalid_planning_policy"})
        self.assertNotIn("automatic", repr(result))

    def test_invalid_route_configuration_returns_privacy_safe_base_error(self) -> None:
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            result = asyncio.run(
                module.MobilityForecastConfigFlow().async_step_user(
                    {
                        "name": "Invalid route",
                        "calendar_entity_ids": ["calendar.synthetic"],
                        **POLICY_INPUT,
                        **{**ROUTE_INPUT, "route_provider_api_key": ""},
                    }
                )
            )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "invalid_route_provider"})

    def test_reconfigure_replaces_provider_specific_fields_without_fallback(
        self,
    ) -> None:
        entry = SimpleNamespace(
            data={
                "calendar_entity_ids": ["calendar.synthetic_existing"],
                **POLICY_INPUT,
                **ROUTE_INPUT,
            }
        )
        self_hosted = {
            **POLICY_INPUT,
            **{
                key: value
                for key, value in ROUTE_INPUT.items()
                if key not in {"route_provider", "route_provider_api_key"}
            },
            "route_provider": "openrouteservice_self_hosted",
            "routing_base_url": "https://routing.synthetic.invalid/ors",
            "geocoder_provider": "pelias",
            "geocoder_base_url": "https://geocoder.synthetic.invalid/pelias",
        }
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            flow = module.MobilityForecastConfigFlow()
            flow.reconfigure_entry = entry
            result = asyncio.run(flow.async_step_reconfigure(self_hosted))

        self.assertEqual(result["type"], "abort")
        self.assertEqual(
            entry.data,
            {
                "calendar_entity_ids": ["calendar.synthetic_existing"],
                **self_hosted,
            },
        )
        self.assertNotIn("route_provider_api_key", entry.data)

    def test_reconfigure_updates_policy_without_replacing_calendar_selection(
        self,
    ) -> None:
        entry = SimpleNamespace(
            data={"calendar_entity_ids": ["calendar.synthetic_existing"]}
        )
        updated_policy = {
            **POLICY_INPUT,
            "physical_event_policy": "exclude",
            "online_event_policy": "include",
            **ROUTE_INPUT,
        }
        with fake_home_assistant():
            module = importlib.import_module(
                "custom_components.mobility_forecast.config_flow"
            )
            flow = module.MobilityForecastConfigFlow()
            flow.reconfigure_entry = entry
            result = asyncio.run(flow.async_step_reconfigure(updated_policy))

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "reconfigure_successful")
        self.assertEqual(
            entry.data,
            {
                "calendar_entity_ids": ["calendar.synthetic_existing"],
                **updated_policy,
            },
        )


if __name__ == "__main__":
    unittest.main()
