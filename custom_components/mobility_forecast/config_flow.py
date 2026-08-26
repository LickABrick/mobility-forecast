"""Config flow for Mobility Forecast profiles."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

DOMAIN = "mobility_forecast"

PROFILE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): str})


class MobilityForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one independent config entry per forecast profile."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a profile without introducing behavioral defaults."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=PROFILE_SCHEMA)

        return self.async_create_entry(title=user_input[CONF_NAME], data={})
