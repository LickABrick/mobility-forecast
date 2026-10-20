"""Native short vehicle setup."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TimeSelector,
)

from .const import DOMAIN
from .odometer import InvalidReading, validate_source

HELP_TARGETS = {
    "user": "getting-started.md#odometer",
    "vehicle": "configuration.md#vehicle",
    "calendars": "calendar-routing.md#setup",
    "routing": "calendar-routing.md#waze",
    "add_location": "calendar-routing.md#known-locations",
    "ev": "ev-charging.md#setup",
    "ev_advanced": "ev-charging.md#advanced-options",
    "ev_entities": "ev-charging.md#vehicle-entities",
}


def help_link(step):
    return {
        "help_url": "https://github.com/LickABrick/mobility-forecast/blob/master/docs/"
        + HELP_TARGETS[step]
    }


def vehicle_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional("name"): TextSelector(),
            vol.Required("odometer"): EntitySelector(
                EntitySelectorConfig(
                    filter=[
                        {"domain": "sensor", "device_class": "distance"},
                        {"domain": "sensor", "unit_of_measurement": ["km", "mi"]},
                    ]
                )
            ),
        }
    )


class MobilityFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                validate_source(self.hass.states.get(user_input["odometer"]))
            except InvalidReading:
                errors["odometer"] = "invalid_source"
            else:
                entity = er.async_get(self.hass).async_get(user_input["odometer"])
                identity = entity.id if entity else user_input["odometer"]
                for other in self._async_current_entries():
                    if other.data["odometer"] == user_input["odometer"] or (
                        entity and other.data.get("registry_id") == entity.id
                    ):
                        return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(identity)
                self._abort_if_unique_id_configured()
                data = {**user_input, "registry_id": entity.id if entity else None}
                title = (
                    user_input.get("name")
                    or self.hass.states.get(user_input["odometer"]).name
                )
                return self.async_create_entry(title=title, data=data)
        return self.async_show_form(
            step_id="user",
            description_placeholders=help_link("user"),
            data_schema=vehicle_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                validate_source(self.hass.states.get(user_input["odometer"]))
            except InvalidReading:
                errors["odometer"] = "invalid_source"
            else:
                entity = er.async_get(self.hass).async_get(user_input["odometer"])
                identity = entity.id if entity else user_input["odometer"]
                for other in self._async_current_entries():
                    if other.entry_id != entry.entry_id and (
                        other.unique_id == identity
                        or other.data["odometer"] == user_input["odometer"]
                    ):
                        return self.async_abort(reason="already_configured")
                # Same entry identity remains stable; runtime verifies continuity before adding values.
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        "odometer": user_input["odometer"],
                        "registry_id": entity.id if entity else None,
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "odometer", default=entry.data["odometer"]
                    ): EntitySelector(
                        EntitySelectorConfig(
                            filter=[
                                {"domain": "sensor", "device_class": "distance"},
                                {
                                    "domain": "sensor",
                                    "unit_of_measurement": ["km", "mi"],
                                },
                            ]
                        )
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MobilityOptions()


class MobilityOptions(config_entries.OptionsFlow):
    """Separate simple settings from the optional location exception editor."""

    def _options(self):
        if not hasattr(self, "draft"):
            self.draft = dict(self.config_entry.options)
            self.draft["known_locations"] = dict(self.draft.get("known_locations", {}))
        return self.draft

    async def async_step_init(self, user_input=None):
        self._options()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "vehicle",
                "calendars",
                "locations",
                "ev_menu",
            ],
        )

    async def async_step_ev_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="ev_menu",
            menu_options=["ev"]
            + (
                ["ev_entities", "ev_advanced"]
                if self._options().get("ev_enabled")
                else []
            )
            + ["init"],
        )

    async def async_step_vehicle(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=user_input["name"]
            )
            return self.async_create_entry(title="", data=self._options())
        return self.async_show_form(
            step_id="vehicle",
            description_placeholders=help_link("vehicle"),
            data_schema=vol.Schema(
                {vol.Required("name", default=self.config_entry.title): TextSelector()}
            ),
        )

    async def async_step_calendars(self, user_input=None):
        options = self._options()
        errors = {}
        if user_input is not None:
            if user_input.get("routing") and not self.hass.services.has_service(
                "waze_travel_time", "get_travel_times"
            ):
                errors["base"] = "routing_unavailable"
            else:
                options.update(user_input)
                if user_input.get("routing"):
                    return await self.async_step_routing()
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="calendars",
            description_placeholders=help_link("calendars"),
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "calendars", default=options.get("calendars", [])
                    ): EntitySelector(
                        EntitySelectorConfig(domain="calendar", multiple=True)
                    ),
                    vol.Optional(
                        "routing", default=options.get("routing", False)
                    ): BooleanSelector(),
                    vol.Optional(
                        "ignore_nested_appointments",
                        default=options.get("ignore_nested_appointments", False),
                    ): BooleanSelector(),
                }
            ),
        )

    async def async_step_routing(self, user_input=None):
        options = self._options()
        if user_input is not None:
            options.update(user_input)
            return self.async_create_entry(title="", data=options)
        field = vol.Required(
            "region",
            **({"default": options["region"]} if options.get("region") else {}),
        )
        return self.async_show_form(
            step_id="routing",
            description_placeholders=help_link("routing"),
            data_schema=vol.Schema(
                {
                    field: SelectSelector(
                        SelectSelectorConfig(options=["eu", "us", "na", "il", "au"])
                    )
                }
            ),
        )

    async def async_step_locations(self, user_input=None):
        aliases = self._options()["known_locations"]
        return self.async_show_menu(
            step_id="locations",
            menu_options=["add_location"]
            + (["edit_location", "remove_location"] if aliases else []),
        )

    async def async_step_add_location(self, user_input=None):
        from .locations import normalize

        errors = {}
        if user_input is not None:
            name = user_input["name"].strip()
            if not name or normalize(user_input["address"]) is None:
                errors["base"] = "invalid_location"
            else:
                aliases = self._options()["known_locations"]
                if any(
                    k.casefold() == name.casefold() for k in aliases
                ) and name != getattr(self, "editing", None):
                    errors["base"] = "duplicate_location"
                else:
                    aliases.pop(getattr(self, "editing", ""), None)
                    aliases[name] = user_input["address"].strip()
                    return self.async_create_entry(title="", data=self._options())
        editing = getattr(self, "editing", "")
        return self.async_show_form(
            step_id="add_location",
            description_placeholders=help_link("add_location"),
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=editing): TextSelector(),
                    vol.Required(
                        "address",
                        default=self._options()["known_locations"].get(editing, ""),
                    ): TextSelector(),
                }
            ),
        )

    async def async_step_edit_location(self, user_input=None):
        if user_input is not None:
            self.editing = user_input["location"]
            return await self.async_step_add_location()
        return self._location_picker("edit_location")

    async def async_step_remove_location(self, user_input=None):
        if user_input is not None:
            self._options()["known_locations"].pop(user_input["location"], None)
            return self.async_create_entry(title="", data=self._options())
        return self._location_picker("remove_location")

    def _location_picker(self, step):
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required("location"): SelectSelector(
                        SelectSelectorConfig(
                            options=list(self._options()["known_locations"])
                        )
                    )
                }
            ),
        )

    async def async_step_ev(self, user_input=None):
        import math

        options = self._options()
        errors = {}
        if user_input is not None:
            if user_input.get("ev_enabled"):
                for key, upper in (
                    ("usable_capacity_kwh", 300),
                    ("consumption_kwh_per_100km", 100),
                    ("max_ac_charge_power_kw", 43),
                ):
                    value = user_input.get(key)
                    if (
                        not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        or not 0 < value <= upper
                    ):
                        errors[key] = "invalid_number"
                state = self.hass.states.get(user_input.get("soc_entity", ""))
                if (
                    state is None
                    or state.domain != "sensor"
                    or state.attributes.get("unit_of_measurement") != "%"
                ):
                    errors["soc_entity"] = "invalid_soc_sensor"
                if (
                    not 0 <= user_input.get("minimum_soc", 15) <= 50
                    or not 50 <= user_input.get("preferred_max_soc", 80) <= 100
                    or user_input.get("minimum_soc", 15)
                    >= user_input.get("preferred_max_soc", 80)
                ):
                    errors["minimum_soc"] = "invalid_reserve"
                if user_input.get(
                    "charging_mode"
                ) != "home_only" and not user_input.get("external_lookup_consent"):
                    errors["external_lookup_consent"] = "consent_required"
            if not errors:
                options.update(user_input)
                return self.async_create_entry(title="", data=options)
        fields = {
            vol.Required(
                "ev_enabled", default=options.get("ev_enabled", False)
            ): BooleanSelector(),
            vol.Optional(
                "soc_entity",
                **(
                    {"default": options["soc_entity"]}
                    if options.get("soc_entity")
                    else {}
                ),
            ): EntitySelector(
                EntitySelectorConfig(
                    filter={"domain": "sensor", "unit_of_measurement": "%"}
                )
            ),
        }
        for key, default in (
            ("usable_capacity_kwh", None),
            ("consumption_kwh_per_100km", None),
            ("max_ac_charge_power_kw", None),
            ("minimum_soc", 15),
            ("preferred_max_soc", 80),
        ):
            value = options.get(key, default)
            fields[
                vol.Optional(key, **({"default": value} if value is not None else {}))
            ] = NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max={
                        "usable_capacity_kwh": 300,
                        "consumption_kwh_per_100km": 100,
                        "max_ac_charge_power_kw": 43,
                        "minimum_soc": 50,
                        "preferred_max_soc": 100,
                    }[key],
                    step=0.1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement={
                        "usable_capacity_kwh": "kWh",
                        "consumption_kwh_per_100km": "kWh/100 km",
                        "max_ac_charge_power_kw": "kW",
                        "minimum_soc": "%",
                        "preferred_max_soc": "%",
                    }[key],
                )
            )
        fields[
            vol.Required(
                "charging_mode", default=options.get("charging_mode", "home_only")
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=["home_only", "home_and_appointments", "appointments_only"],
                translation_key="charging_mode",
            )
        )
        fields[
            vol.Optional(
                "external_lookup_consent",
                default=options.get("external_lookup_consent", False),
            )
        ] = BooleanSelector()
        return self.async_show_form(
            step_id="ev",
            description_placeholders=help_link("ev"),
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_ev_advanced(self, user_input=None):
        import math
        from datetime import time

        options = self._options()
        errors = {}
        bounds = {
            "session_overhead_minutes": (0, 120, 15),
            "minimum_useful_charge_kwh": (0, 100, 5),
            "absolute_max_soc": (50, 100, 100),
        }
        if options.get("charging_mode", "home_only") != "home_only":
            bounds.update(
                minimum_appointment_minutes=(1, 1440, 90),
                max_charger_distance_m=(1, 1000, 300),
            )
        if user_input is not None:
            for key, (low, high, _) in bounds.items():
                value = user_input.get(key)
                if (
                    not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not low <= value <= high
                ):
                    errors[key] = "invalid_number"
            for key in ("home_window_start", "home_window_end"):
                if key in user_input:
                    try:
                        time.fromisoformat(user_input[key])
                    except ValueError, TypeError:
                        errors[key] = "invalid_time"
            if user_input.get("absolute_max_soc", 100) < options.get(
                "preferred_max_soc", 80
            ):
                errors["absolute_max_soc"] = "invalid_ev"
            if not errors:
                options.update(user_input)
                return self.async_create_entry(title="", data=options)
        fields = {
            vol.Required(key, default=options.get(key, default)): NumberSelector(
                NumberSelectorConfig(
                    min=low,
                    max=high,
                    step=0.1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement={
                        "session_overhead_minutes": "min",
                        "minimum_useful_charge_kwh": "kWh",
                        "absolute_max_soc": "%",
                        "minimum_appointment_minutes": "min",
                        "max_charger_distance_m": "m",
                    }[key],
                )
            )
            for key, (low, high, default) in bounds.items()
        }
        for key, default in (
            ("prefer_long_sessions", True),
            ("allow_above_preferred_soc", False),
        ):
            fields[vol.Required(key, default=options.get(key, default))] = (
                BooleanSelector()
            )
        if options.get("charging_mode", "home_only") != "appointments_only":
            for key, default in (
                ("home_window_start", "18:00"),
                ("home_window_end", "07:00"),
            ):
                fields[vol.Required(key, default=options.get(key, default))] = (
                    TimeSelector()
                )
        return self.async_show_form(
            step_id="ev_advanced",
            description_placeholders=help_link("ev_advanced"),
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_ev_entities(self, user_input=None):
        from .ev.vehicle import OPTIONAL_UNITS

        options = self._options()
        errors = {}
        if user_input is not None:
            for key, entity_id in user_input.items():
                state = self.hass.states.get(entity_id) if entity_id else None
                allowed = (
                    ["sensor"]
                    if key in OPTIONAL_UNITS
                    else ["sensor", "binary_sensor", "device_tracker"]
                )
                if entity_id and entity_id.split(".", 1)[0] not in allowed:
                    errors[key] = "invalid_ev"
                elif (
                    state is not None
                    and key in OPTIONAL_UNITS
                    and state.attributes.get("unit_of_measurement")
                    not in OPTIONAL_UNITS[key]
                ):
                    errors[key] = "invalid_number"
            if not errors:
                for key in (
                    *OPTIONAL_UNITS,
                    "charging_state_entity",
                    "plugged_in_entity",
                    "vehicle_location_entity",
                ):
                    options.pop(key, None)
                # Empty markers preserve an explicit clear and suppress future suggestions.
                options.update(
                    {
                        key: user_input.get(key, "")
                        for key in (
                            *OPTIONAL_UNITS,
                            "charging_state_entity",
                            "plugged_in_entity",
                            "vehicle_location_entity",
                        )
                    }
                )
                return self.async_create_entry(title="", data=options)
        suggestions = self._entity_suggestions()
        fields = {}
        for key in (
            *OPTIONAL_UNITS,
            "charging_state_entity",
            "plugged_in_entity",
            "vehicle_location_entity",
        ):
            fields[
                vol.Optional(
                    key,
                    **(
                        {"default": options[key]}
                        if options.get(key)
                        else {"description": {"suggested_value": suggestions[key]}}
                        if key in suggestions and key not in options
                        else {}
                    ),
                )
            ] = EntitySelector(
                EntitySelectorConfig(
                    domain=["sensor"]
                    if key in OPTIONAL_UNITS
                    else ["sensor", "binary_sensor", "device_tracker"]
                )
            )
        return self.async_show_form(
            step_id="ev_entities",
            description_placeholders=help_link("ev_entities"),
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    def _entity_suggestions(self):
        """Suggest only unambiguous same-device numeric semantics; never persist here."""
        from .ev.vehicle import OPTIONAL_UNITS

        registry = er.async_get(self.hass)
        source = registry.async_get(self._options().get("soc_entity", ""))
        if source is None or source.device_id is None:
            return {}
        classes = {
            "range_entity": "distance",
            "charging_power_entity": "power",
            "remaining_charge_time_entity": "duration",
        }
        result = {}
        for key, device_class in classes.items():
            candidates = []
            for entity in er.async_entries_for_device(registry, source.device_id):
                state = self.hass.states.get(entity.entity_id)
                if (
                    entity.domain == "sensor"
                    and not entity.disabled
                    and state is not None
                    and state.state not in ("unknown", "unavailable")
                    and state.attributes.get("device_class") == device_class
                    and state.attributes.get("unit_of_measurement")
                    in OPTIONAL_UNITS[key]
                ):
                    candidates.append(entity.entity_id)
            if len(candidates) == 1:
                result[key] = candidates[0]
        return result
