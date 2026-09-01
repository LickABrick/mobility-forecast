"""Config flow for Mobility Forecast profiles."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .ha_calendar import (
    CONF_CALENDAR_ENTITY_IDS,
    validate_calendar_entity_ids,
)

DOMAIN = "mobility_forecast"


def _validate_calendar_entity_ids(value: object) -> list[str]:
    """Translate the pure config validator into a Voluptuous error."""

    try:
        return validate_calendar_entity_ids(value)
    except ValueError as err:
        raise vol.Invalid("select at least one calendar entity") from err


PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_CALENDAR_ENTITY_IDS): EntitySelector(
            EntitySelectorConfig(domain="calendar", multiple=True)
        ),
    }
)


class MobilityForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one independent config entry per forecast profile."""

    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a profile without introducing behavioral defaults."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=PROFILE_SCHEMA)

        try:
            entity_ids = _validate_calendar_entity_ids(
                user_input[CONF_CALENDAR_ENTITY_IDS]
            )
        except vol.Invalid:
            return self.async_show_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={CONF_CALENDAR_ENTITY_IDS: "calendar_required"},
            )
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={CONF_CALENDAR_ENTITY_IDS: entity_ids},
        )
