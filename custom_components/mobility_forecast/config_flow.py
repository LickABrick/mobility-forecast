"""Config flow for Mobility Forecast profiles."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .forecast_config import (
    CONF_COLD_START_P90_PERCENT,
    CONF_MAXIMUM_CORRECTION_PERCENT,
    CONF_MINIMUM_CORRECTION_PERCENT,
    CONF_MINIMUM_HISTORY_SAMPLES,
    MAXIMUM_COLD_START_P90_PERCENT,
    MAXIMUM_CORRECTION_PERCENT,
    MAXIMUM_HISTORY_SAMPLES,
    MINIMUM_COLD_START_P90_PERCENT,
    MINIMUM_CORRECTION_PERCENT,
    ProfileForecastConfig,
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
from .provider_guardrails import (
    MAX_GEOCODE_CACHE_RETENTION,
    MAX_GEOCODE_REQUESTS_PER_REFRESH,
    MAX_REQUEST_ATTEMPTS,
    MAX_REQUEST_TIMEOUT,
    MAX_ROUTE_REQUESTS_PER_REFRESH,
)
from .route_provider_config import (
    CONF_GEOCODE_CACHE_RETENTION_HOURS,
    CONF_GEOCODER_BASE_URL,
    CONF_GEOCODER_PROVIDER,
    CONF_HIGHWAY_POLICY,
    CONF_LOCATION_DATA_CONSENT,
    CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH,
    CONF_MAX_REQUEST_ATTEMPTS,
    CONF_MAX_ROUTE_REQUESTS_PER_REFRESH,
    CONF_REQUEST_TIMEOUT_SECONDS,
    CONF_ROUTE_CACHE_FRESH_HOURS,
    CONF_ROUTE_CACHE_STALE_HOURS,
    CONF_ROUTE_PROVIDER,
    CONF_ROUTE_PROVIDER_API_KEY,
    CONF_ROUTING_BASE_URL,
    CONF_TOLL_POLICY,
    GEOAPIFY_GEOCODING_ENDPOINT,
    GEOAPIFY_ROUTING_ENDPOINT,
    GOOGLE_GEOCODING_ENDPOINT,
    GOOGLE_ROUTING_ENDPOINT,
    MAX_ROUTE_CACHE_FRESH_HOURS,
    MAX_ROUTE_CACHE_STALE_HOURS,
    ORS_HOSTED_GEOCODING_ENDPOINT,
    ORS_HOSTED_ROUTING_ENDPOINT,
    GeocoderKind,
    LocationDataConsent,
    ProfileRouteConfig,
    RoutePreference,
    RouteProviderKind,
)

DOMAIN = "mobility_forecast"
_POLICY_CHOICES = {
    "": "Select explicitly",
    EventHandling.INCLUDE.value: "Include",
    EventHandling.EXCLUDE.value: "Exclude",
}
_ROUTE_PROVIDER_CHOICES = {
    "": "Select explicitly",
    RouteProviderKind.OPENROUTESERVICE_HOSTED.value: (
        "OpenRouteService hosted (recommended)"
    ),
    RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED.value: (
        "Self-hosted OpenRouteService + separate geocoder"
    ),
    RouteProviderKind.GEOAPIFY.value: "Geoapify",
    RouteProviderKind.GOOGLE.value: "Google Routes + Geocoding",
}
_GEOCODER_CHOICES = {
    "": "Not applicable for hosted providers",
    GeocoderKind.PELIAS.value: "Pelias",
    GeocoderKind.PHOTON.value: "Photon",
    GeocoderKind.NOMINATIM.value: "Nominatim",
}
_CONSENT_CHOICES = {
    "": "Select explicitly",
    LocationDataConsent.ACCEPTED.value: "I understand and consent",
}
_ROUTE_PREFERENCE_CHOICES = {
    "": "Select explicitly",
    RoutePreference.ALLOW.value: "Allow",
    RoutePreference.AVOID.value: "Avoid",
}
_ENDPOINT_DESCRIPTION_PLACEHOLDERS = {
    "ors_geocoding_endpoint": ORS_HOSTED_GEOCODING_ENDPOINT,
    "ors_routing_endpoint": ORS_HOSTED_ROUTING_ENDPOINT,
    "geoapify_geocoding_endpoint": GEOAPIFY_GEOCODING_ENDPOINT,
    "geoapify_routing_endpoint": GEOAPIFY_ROUTING_ENDPOINT,
    "google_geocoding_endpoint": GOOGLE_GEOCODING_ENDPOINT,
    "google_routing_endpoint": GOOGLE_ROUTING_ENDPOINT,
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


def _number_selector(maximum: int, *, minimum: int = 1) -> NumberSelector:
    """Build an explicit integer selector with no default."""

    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
        )
    )


def _route_schema_fields() -> dict[object, object]:
    """Build explicit provider, consent and transport-safety fields without defaults."""

    return {
        vol.Required(CONF_ROUTE_PROVIDER): vol.In(_ROUTE_PROVIDER_CHOICES),
        vol.Optional(CONF_ROUTE_PROVIDER_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_ROUTING_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_GEOCODER_PROVIDER): vol.In(_GEOCODER_CHOICES),
        vol.Optional(CONF_GEOCODER_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_LOCATION_DATA_CONSENT): vol.In(_CONSENT_CHOICES),
        vol.Required(CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH): _number_selector(
            MAX_GEOCODE_REQUESTS_PER_REFRESH
        ),
        vol.Required(CONF_MAX_ROUTE_REQUESTS_PER_REFRESH): _number_selector(
            MAX_ROUTE_REQUESTS_PER_REFRESH
        ),
        vol.Required(CONF_MAX_REQUEST_ATTEMPTS): _number_selector(MAX_REQUEST_ATTEMPTS),
        vol.Required(CONF_REQUEST_TIMEOUT_SECONDS): _number_selector(
            int(MAX_REQUEST_TIMEOUT.total_seconds())
        ),
        vol.Required(CONF_GEOCODE_CACHE_RETENTION_HOURS): _number_selector(
            int(MAX_GEOCODE_CACHE_RETENTION.total_seconds() // 3600)
        ),
        vol.Required(CONF_ROUTE_CACHE_FRESH_HOURS): _number_selector(
            MAX_ROUTE_CACHE_FRESH_HOURS
        ),
        vol.Required(CONF_ROUTE_CACHE_STALE_HOURS): _number_selector(
            MAX_ROUTE_CACHE_STALE_HOURS
        ),
        vol.Required(CONF_TOLL_POLICY): vol.In(_ROUTE_PREFERENCE_CHOICES),
        vol.Required(CONF_HIGHWAY_POLICY): vol.In(_ROUTE_PREFERENCE_CHOICES),
    }


def _forecast_schema_fields() -> dict[object, object]:
    """Build explicit uncertainty settings without behavioral defaults."""

    return {
        vol.Required(CONF_MINIMUM_HISTORY_SAMPLES): _number_selector(
            MAXIMUM_HISTORY_SAMPLES
        ),
        vol.Required(CONF_MINIMUM_CORRECTION_PERCENT): _number_selector(
            MAXIMUM_CORRECTION_PERCENT, minimum=MINIMUM_CORRECTION_PERCENT
        ),
        vol.Required(CONF_MAXIMUM_CORRECTION_PERCENT): _number_selector(
            MAXIMUM_CORRECTION_PERCENT, minimum=MINIMUM_CORRECTION_PERCENT
        ),
        vol.Required(CONF_COLD_START_P90_PERCENT): _number_selector(
            MAXIMUM_COLD_START_P90_PERCENT,
            minimum=MINIMUM_COLD_START_P90_PERCENT,
        ),
    }


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_ENTITY_IDS): EntitySelector(
            EntitySelectorConfig(domain="calendar", multiple=True)
        ),
        **_planning_schema_fields(),
        **_route_schema_fields(),
        **_forecast_schema_fields(),
    }
)
PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_CALENDAR_ENTITY_IDS): EntitySelector(
            EntitySelectorConfig(domain="calendar", multiple=True)
        ),
        **_planning_schema_fields(),
        **_route_schema_fields(),
        **_forecast_schema_fields(),
    }
)


def _validated_planning_data(user_input: dict[str, Any]) -> dict[str, str]:
    """Return strict JSON-safe planning data or raise a fixed validation error."""

    try:
        return ProfilePlanningConfig.from_entry_data(user_input).as_entry_data()
    except ValueError as err:
        raise vol.Invalid("invalid planning policy") from err


def _validated_route_data(user_input: dict[str, Any]) -> dict[str, str | int]:
    """Return strict private route configuration or a fixed validation error."""

    normalized = dict(user_input)
    for key in (
        CONF_ROUTING_BASE_URL,
        CONF_GEOCODER_PROVIDER,
        CONF_GEOCODER_BASE_URL,
    ):
        if normalized.get(key) == "":
            normalized.pop(key)
    if (
        normalized.get(CONF_ROUTE_PROVIDER)
        == RouteProviderKind.OPENROUTESERVICE_SELF_HOSTED.value
        and normalized.get(CONF_ROUTE_PROVIDER_API_KEY) == ""
    ):
        normalized.pop(CONF_ROUTE_PROVIDER_API_KEY)
    try:
        return ProfileRouteConfig.from_entry_data(normalized).as_entry_data()
    except ValueError as err:
        raise vol.Invalid("invalid route provider configuration") from err


def _validated_forecast_data(user_input: dict[str, Any]) -> dict[str, int]:
    """Return strict explicit model policy or a fixed validation error."""

    try:
        return ProfileForecastConfig.from_entry_data(user_input).as_entry_data()
    except ValueError as err:
        raise vol.Invalid("invalid forecast policy") from err


class MobilityForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure independent forecast profiles."""

    VERSION = 1
    MINOR_VERSION = 6

    def _show_profile_form(
        self,
        *,
        step_id: str,
        data_schema: Any,
        errors: dict[str, str] | None = None,
        suggested_values: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show a profile form with endpoint disclosure and nonsecret suggestions."""

        safe_suggestions = (
            None
            if suggested_values is None
            else {
                key: value
                for key, value in suggested_values.items()
                if key != CONF_ROUTE_PROVIDER_API_KEY
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                data_schema, safe_suggestions
            ),
            errors=errors,
            description_placeholders=_ENDPOINT_DESCRIPTION_PLACEHOLDERS,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a profile from explicit source, planning, provider and consent."""

        if user_input is None:
            return self._show_profile_form(step_id="user", data_schema=PROFILE_SCHEMA)

        try:
            entity_ids = _validate_calendar_entity_ids(
                user_input[CONF_CALENDAR_ENTITY_IDS]
            )
        except vol.Invalid:
            return self._show_profile_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={CONF_CALENDAR_ENTITY_IDS: "calendar_required"},
                suggested_values=user_input,
            )
        try:
            planning_data = _validated_planning_data(user_input)
        except vol.Invalid:
            return self._show_profile_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={"base": "invalid_planning_policy"},
                suggested_values=user_input,
            )
        try:
            route_data = _validated_route_data(user_input)
        except vol.Invalid:
            return self._show_profile_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={"base": "invalid_route_provider"},
                suggested_values=user_input,
            )
        try:
            forecast_data = _validated_forecast_data(user_input)
        except vol.Invalid:
            return self._show_profile_form(
                step_id="user",
                data_schema=PROFILE_SCHEMA,
                errors={"base": "invalid_forecast_policy"},
                suggested_values=user_input,
            )
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_CALENDAR_ENTITY_IDS: entity_ids,
                **planning_data,
                **route_data,
                **forecast_data,
            },
        )

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure sources and policy without suggesting the private credential."""

        entry = self._get_reconfigure_entry()
        if user_input is None:
            return self._show_profile_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                suggested_values=dict(entry.data),
            )
        try:
            entity_ids = _validate_calendar_entity_ids(
                user_input[CONF_CALENDAR_ENTITY_IDS]
            )
        except (KeyError, vol.Invalid):
            return self._show_profile_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                errors={CONF_CALENDAR_ENTITY_IDS: "calendar_required"},
                suggested_values=user_input,
            )
        try:
            planning_data = _validated_planning_data(user_input)
        except vol.Invalid:
            return self._show_profile_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_planning_policy"},
                suggested_values=user_input,
            )
        try:
            route_data = _validated_route_data(user_input)
        except vol.Invalid:
            return self._show_profile_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_route_provider"},
                suggested_values=user_input,
            )
        try:
            forecast_data = _validated_forecast_data(user_input)
        except vol.Invalid:
            return self._show_profile_form(
                step_id="reconfigure",
                data_schema=CONFIG_SCHEMA,
                errors={"base": "invalid_forecast_policy"},
                suggested_values=user_input,
            )
        return self.async_update_reload_and_abort(
            entry,
            data={
                CONF_CALENDAR_ENTITY_IDS: entity_ids,
                **planning_data,
                **route_data,
                **forecast_data,
            },
        )
