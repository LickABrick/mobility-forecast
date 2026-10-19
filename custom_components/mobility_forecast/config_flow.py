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
    ObjectSelector,
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
                EntitySelectorConfig(domain="sensor")
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
                    ): EntitySelector(EntitySelectorConfig(domain="sensor"))
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MobilityOptions()


class MobilityOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=user_input["name"]
            )
            if user_input.get("routing") and not user_input.get("region"):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(),
                    errors={"base": "region_required"},
                )
            aliases = user_input.get("known_locations", {})
            if not isinstance(aliases, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(),
                    errors={"base": "invalid_locations"},
                )
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=self._schema())

    def _schema(self):
        return vol.Schema(
            {
                vol.Required("name", default=self.config_entry.title): TextSelector(),
                vol.Optional(
                    "calendars",
                    default=self.config_entry.options.get("calendars", []),
                ): EntitySelector(
                    EntitySelectorConfig(domain="calendar", multiple=True)
                ),
                vol.Optional(
                    "routing", default=self.config_entry.options.get("routing", False)
                ): BooleanSelector(),
                vol.Optional(
                    "region", default=self.config_entry.options.get("region", "eu")
                ): SelectSelector(SelectSelectorConfig(options=["eu", "us", "il"])),
                vol.Optional(
                    "known_locations",
                    default=self.config_entry.options.get("known_locations", {}),
                ): ObjectSelector(),
            }
        )
