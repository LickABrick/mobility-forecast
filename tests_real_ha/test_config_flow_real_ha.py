"""Config-flow compatibility tests against Home Assistant 2026.8.1."""

from __future__ import annotations

from importlib.metadata import version
from typing import Any

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.config_flow import DOMAIN
from custom_components.mobility_forecast.forecast_config import (
    CONF_COLD_START_P90_PERCENT,
    CONF_MAXIMUM_CORRECTION_PERCENT,
    CONF_MINIMUM_CORRECTION_PERCENT,
    CONF_MINIMUM_HISTORY_SAMPLES,
)
from custom_components.mobility_forecast.ha_calendar import CONF_CALENDAR_ENTITY_IDS
from custom_components.mobility_forecast.profile_config import (
    CONF_ALL_DAY_EVENT_POLICY,
    CONF_END_ANCHOR_ENTITY_ID,
    CONF_NO_LOCATION_EVENT_POLICY,
    CONF_ONLINE_EVENT_POLICY,
    CONF_PHYSICAL_EVENT_POLICY,
    CONF_START_ANCHOR_ENTITY_ID,
)
from custom_components.mobility_forecast.route_provider_config import (
    CONF_GEOCODE_CACHE_RETENTION_HOURS,
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
    CONF_TOLL_POLICY,
)

PLANNING_INPUT = {
    CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
    CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
    CONF_PHYSICAL_EVENT_POLICY: "include",
    CONF_ONLINE_EVENT_POLICY: "exclude",
    CONF_ALL_DAY_EVENT_POLICY: "exclude",
    CONF_NO_LOCATION_EVENT_POLICY: "exclude",
}
ROUTE_INPUT = {
    CONF_ROUTE_PROVIDER: "openrouteservice_hosted",
    CONF_ROUTE_PROVIDER_API_KEY: "synthetic-test-key",
    CONF_LOCATION_DATA_CONSENT: "accepted",
    CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH: 8,
    CONF_MAX_ROUTE_REQUESTS_PER_REFRESH: 16,
    CONF_MAX_REQUEST_ATTEMPTS: 2,
    CONF_REQUEST_TIMEOUT_SECONDS: 10,
    CONF_GEOCODE_CACHE_RETENTION_HOURS: 72,
    CONF_ROUTE_CACHE_FRESH_HOURS: 6,
    CONF_ROUTE_CACHE_STALE_HOURS: 24,
    CONF_TOLL_POLICY: "avoid",
    CONF_HIGHWAY_POLICY: "allow",
}
FORECAST_INPUT = {
    CONF_MINIMUM_HISTORY_SAMPLES: 5,
    CONF_MINIMUM_CORRECTION_PERCENT: 60,
    CONF_MAXIMUM_CORRECTION_PERCENT: 180,
    CONF_COLD_START_P90_PERCENT: 125,
}


async def test_user_flow_creates_explicit_synthetic_profile(
    hass: HomeAssistant,
) -> None:
    """Exercise selector schema and entry creation through HA's real flow manager."""

    assert version("homeassistant") == "2026.8.1"

    form: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "user"
    assert form["errors"] is None
    assert form["description_placeholders"] == {
        "ors_geocoding_endpoint": "https://api.openrouteservice.org/geocode/search",
        "ors_routing_endpoint": (
            "https://api.openrouteservice.org/v2/directions/driving-car"
        ),
        "geoapify_geocoding_endpoint": "https://api.geoapify.com/v1/geocode/search",
        "geoapify_routing_endpoint": "https://api.geoapify.com/v1/routing",
        "google_geocoding_endpoint": (
            "https://maps.googleapis.com/maps/api/geocode/json"
        ),
        "google_routing_endpoint": (
            "https://routes.googleapis.com/directions/v2:computeRoutes"
        ),
    }
    expected_input = {
        CONF_NAME: "Synthetic commute",
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
        **PLANNING_INPUT,
        **ROUTE_INPUT,
        **FORECAST_INPUT,
    }
    assert form["data_schema"](expected_input) == expected_input

    result: dict[str, Any] = await hass.config_entries.flow.async_configure(
        form["flow_id"], user_input=expected_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Synthetic commute"
    assert result["data"] == {
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_work"],
        **PLANNING_INPUT,
        **ROUTE_INPUT,
        **FORECAST_INPUT,
    }
    assert result["result"].version == 1
    assert result["result"].minor_version == 6


async def test_reconfigure_preserves_calendar_and_updates_explicit_policy(
    hass: HomeAssistant,
) -> None:
    """Exercise Home Assistant's real reconfigure update/reload helper."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic existing profile",
        data={CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_existing"]},
        version=1,
        minor_version=5,
    )
    entry.add_to_hass(hass)
    form: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "reconfigure"
    result: dict[str, Any] = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        user_input={**PLANNING_INPUT, **ROUTE_INPUT, **FORECAST_INPUT},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_existing"],
        **PLANNING_INPUT,
        **ROUTE_INPUT,
        **FORECAST_INPUT,
    }
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
