"""Native short vehicle setup."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
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
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name", default=self.config_entry.title
                    ): TextSelector(),
                    vol.Optional(
                        "calendars",
                        default=self.config_entry.options.get("calendars", []),
                    ): EntitySelector(
                        EntitySelectorConfig(domain="calendar", multiple=True)
                    ),
                }
            ),
        )
