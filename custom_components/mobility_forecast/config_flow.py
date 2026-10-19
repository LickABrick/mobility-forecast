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
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import DOMAIN
from .odometer import InvalidReading, validate_source


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
            step_id="user", data_schema=vehicle_schema(), errors=errors
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
            step_id="init", menu_options=["vehicle", "calendars", "locations"]
        )

    async def async_step_vehicle(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=user_input["name"]
            )
            return self.async_create_entry(title="", data=self._options())
        return self.async_show_form(
            step_id="vehicle",
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
