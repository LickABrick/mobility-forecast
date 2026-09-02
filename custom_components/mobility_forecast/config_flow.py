"""Config flow for Mobility Forecast profiles."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .ha_calendar import (
    CONF_CALENDAR_ENTITY_IDS,
    validate_calendar_entity_ids,
)
from .profile_config import (
    CONF_ALL_DAY_EVENT_POLICY,
    CONF_END_ANCHOR_ENTITY_ID,
    CONF_NO_LOCATION_EVENT_POLICY,
    CONF_ONLINE_EVENT_POLICY,
    CONF_PHYSICAL_EVENT_POLICY,
    CONF_START_ANCHOR_ENTITY_ID,
    EventHandling,
    ProfilePlanningConfig,
)
from .route_provider_config import (
    CONF_HIGHWAY_POLICY,
    CONF_ROUTE_PROVIDER,
    CONF_ROUTE_PROVIDER_API_KEY,
    CONF_TOLL_POLICY,
    ProfileRouteConfig,
    RoutePreference,
    RouteProviderKind,
)

DOMAIN = "mobility_forecast"
_POLICY_CHOICES = {
    EventHandling.INCLUDE.value: "Include",
    EventHandling.EXCLUDE.value: "Exclude",
}
_ROUTE_PROVIDER_CHOICES = {
    RouteProviderKind.GOOGLE_ROUTES.value: "Google Routes",
}
_ROUTE_PREFERENCE_CHOICES = {
    RoutePreference.ALLOW.value: "Allow",
    RoutePreference.AVOID.value: "Avoid",
}


def _validate_calendar_entity_ids(value: object) -> list[str]:
    """Translate the pure config validator into a Voluptuous error."""

    try:
        return validate_calendar_entity_ids(value)
    except ValueError as err:
        raise vol.Invalid("select at least one calendar entity") from err


def _planning_schema_fields() -> dict[object, object]:
    """Build required serializable planning fields without defaults."""

    return {
        vol.Required(CONF_START_ANCHOR_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain="zone")
        ),
        vol.Required(CONF_END_ANCHOR_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain="zone")
        ),
        vol.Required(CONF_PHYSICAL_EVENT_POLICY): vol.In(_POLICY_CHOICES),
        vol.Required(CONF_ONLINE_EVENT_POLICY): vol.In(_POLICY_CHOICES),
        vol.Required(CONF_ALL_DAY_EVENT_POLICY): vol.In(_POLICY_CHOICES),
        vol.Required(CONF_NO_LOCATION_EVENT_POLICY): vol.In(_POLICY_CHOICES),
    }


def _route_schema_fields() -> dict[object, object]:
    """Build required serializable route-provider fields without defaults."""

    return {
        vol.Required(CONF_ROUTE_PROVIDER): vol.In(_ROUTE_PROVIDER_CHOICES),
        vol.Required(CONF_ROUTE_PROVIDER_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_TOLL_POLICY): vol.In(_ROUTE_PREFERENCE_CHOICES),
        vol.Required(CONF_HIGHWAY_POLICY): vol.In(_ROUTE_PREFERENCE_CHOICES),
    }


CONFIG_SCHEMA = vol.Schema({**_planning_schema_fields(), **_route_schema_fields()})
PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_CALENDAR_ENTITY_IDS): EntitySelector(
            EntitySelectorConfig(domain="calendar", multiple=True)
        ),
        **_planning_schema_fields(),
        **_route_schema_fields(),
    }
)


def _validated_planning_data(user_input: dict[str, Any]) -> dict[str, str]:
    """Return strict JSON-safe planning data or raise a fixed validation error."""

    try:
        return ProfilePlanningConfig.from_entry_data(user_input).as_entry_data()
    except ValueError as err:
        raise vol.Invalid("invalid planning policy") from err


def _validated_route_data(user_input: dict[str, Any]) -> dict[str, str]:
    """Return strict private route configuration or a fixed validation error."""

    try:
        return ProfileRouteConfig.from_entry_data(user_input).as_entry_data()
    except ValueError as err:
        raise vol.Invalid("invalid route provider configuration") from err


class MobilityForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure independent forecast profiles."""

    VERSION = 1
    MINOR_VERSION = 4

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a profile from explicit source, planning, and route choices."""

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
        try:
            planning_data = _validated_planning_data(user_input)
        except vol.Invalid:
            return self.async_show_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={"base": "invalid_planning_policy"},
            )
        try:
            route_data = _validated_route_data(user_input)
        except vol.Invalid:
            return self.async_show_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={"base": "invalid_route_provider"},
            )
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_CALENDAR_ENTITY_IDS: entity_ids,
                **planning_data,
                **route_data,
            },
        )

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure planning and routing while preserving selected calendars."""

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure", data_schema=CONFIG_SCHEMA
            )
        try:
            planning_data = _validated_planning_data(user_input)
        except vol.Invalid:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_planning_policy"},
            )
        try:
            route_data = _validated_route_data(user_input)
        except vol.Invalid:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_route_provider"},
            )
        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(),
            data_updates={**planning_data, **route_data},
        )
