"""Lifecycle and entity compatibility tests against Home Assistant 2026.8.1."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.config_flow import DOMAIN
from custom_components.mobility_forecast.domain.models import SourceEvent
from custom_components.mobility_forecast.forecast_config import (
    CONF_COLD_START_P90_PERCENT,
    CONF_MAXIMUM_CORRECTION_PERCENT,
    CONF_MINIMUM_CORRECTION_PERCENT,
    CONF_MINIMUM_HISTORY_SAMPLES,
)
from custom_components.mobility_forecast.ha_calendar import (
    CONF_CALENDAR_ENTITY_IDS,
    HomeAssistantCalendarSource,
)
from custom_components.mobility_forecast.openrouteservice import (
    ORS_HOSTED_GEOCODING_ENDPOINT,
    ORS_HOSTED_ROUTING_ENDPOINT,
)
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


async def test_entry_lifecycle_registers_unavailable_read_only_sensor(
    hass: HomeAssistant,
) -> None:
    """Let Home Assistant drive setup, state registration, and clean unload."""

    assert version("homeassistant") == "2026.8.1"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic lifecycle profile",
        data={
            CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_lifecycle"],
            CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
            CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
            CONF_PHYSICAL_EVENT_POLICY: "include",
            CONF_ONLINE_EVENT_POLICY: "exclude",
            CONF_ALL_DAY_EVENT_POLICY: "exclude",
            CONF_NO_LOCATION_EVENT_POLICY: "exclude",
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
            CONF_MINIMUM_HISTORY_SAMPLES: 5,
            CONF_MINIMUM_CORRECTION_PERCENT: 60,
            CONF_MAXIMUM_CORRECTION_PERCENT: 180,
            CONF_COLD_START_P90_PERCENT: 125,
        },
        version=1,
        minor_version=6,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_forecast_distance"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["unit_of_measurement"] == UnitOfLength.KILOMETERS
    assert "service_date" not in state.attributes
    assert "distance_p50_km" not in state.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(entry, "runtime_data")
    restored_state = hass.states.get(entity_id)
    assert restored_state is not None
    assert restored_state.state == STATE_UNAVAILABLE
    assert restored_state.attributes["restored"] is True


async def test_routed_runtime_publishes_and_restores_cached_real_ha_forecast(
    hass: HomeAssistant,
    aioclient_mock,
) -> None:
    """Prove the production runtime through HA while intercepting provider HTTP."""

    starts_at = datetime.now(UTC) + timedelta(days=1)
    event = SourceEvent(
        source_id="calendar.synthetic_routed",
        event_id="synthetic-routed-event",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        all_day=False,
        is_online=False,
        summary="Synthetic routed appointment",
        location_text="Synthetic destination",
    )

    async def synthetic_calendar_read(self, window_start, window_end):
        del self, window_start, window_end
        return (event,)

    aioclient_mock.get(
        re.compile(rf"^{re.escape(ORS_HOSTED_GEOCODING_ENDPOINT)}"),
        json={"features": [{"geometry": {"type": "Point", "coordinates": [-33, 13]}}]},
    )
    aioclient_mock.post(
        ORS_HOSTED_ROUTING_ENDPOINT,
        json={"routes": [{"summary": {"distance": 10000, "duration": 900}}]},
    )
    hass.states.async_set(
        "zone.synthetic_start", "zoning", {"latitude": 12.0, "longitude": -34.0}
    )
    hass.states.async_set(
        "zone.synthetic_end", "zoning", {"latitude": 12.5, "longitude": -33.5}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic routed profile",
        data={
            CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_routed"],
            CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
            CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
            CONF_PHYSICAL_EVENT_POLICY: "include",
            CONF_ONLINE_EVENT_POLICY: "exclude",
            CONF_ALL_DAY_EVENT_POLICY: "exclude",
            CONF_NO_LOCATION_EVENT_POLICY: "exclude",
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
            CONF_MINIMUM_HISTORY_SAMPLES: 5,
            CONF_MINIMUM_CORRECTION_PERCENT: 60,
            CONF_MAXIMUM_CORRECTION_PERCENT: 180,
            CONF_COLD_START_P90_PERCENT: 125,
        },
        version=1,
        minor_version=6,
    )
    entry.add_to_hass(hass)

    with patch.object(
        HomeAssistantCalendarSource,
        "async_read",
        synthetic_calendar_read,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_forecast_distance"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "12.5"
        assert state.attributes["distance_p50_km"] == 10.0
        assert state.attributes["quality"] == "partial"
        assert aioclient_mock.call_count == 2
        geocode_method, geocode_url, _, geocode_headers = aioclient_mock.mock_calls[0]
        route_method, route_url, _, route_headers = aioclient_mock.mock_calls[1]
        assert geocode_method == "GET"
        assert str(geocode_url.with_query(None)) == ORS_HOSTED_GEOCODING_ENDPOINT
        assert geocode_url.query == {
            "text": "Synthetic destination",
            "size": "1",
            "api_key": "synthetic-test-key",
        }
        assert "Authorization" not in geocode_headers
        assert route_method == "POST"
        assert str(route_url) == ORS_HOSTED_ROUTING_ENDPOINT
        assert route_headers["Authorization"] == "synthetic-test-key"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        restored = hass.states.get(entity_id)
        assert restored is not None
        assert restored.state == "12.5"
        assert aioclient_mock.call_count == 2

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_hosted_provider_rejection_stays_unknown_and_private(
    hass: HomeAssistant,
    aioclient_mock,
    caplog,
) -> None:
    """Prove a hosted rejection cannot route, leak values, or become zero."""

    private_location = "Synthetic private destination marker"
    private_key = "synthetic-private-rejected-key"
    provider_echo = "synthetic provider private echo"
    starts_at = datetime.now(UTC) + timedelta(days=1)
    event = SourceEvent(
        source_id="calendar.synthetic_rejected",
        event_id="synthetic-rejected-event",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        all_day=False,
        is_online=False,
        summary="Synthetic rejected appointment",
        location_text=private_location,
    )

    async def synthetic_calendar_read(self, window_start, window_end):
        del self, window_start, window_end
        return (event,)

    aioclient_mock.get(
        re.compile(rf"^{re.escape(ORS_HOSTED_GEOCODING_ENDPOINT)}"),
        status=401,
        text=provider_echo,
    )
    hass.states.async_set(
        "zone.synthetic_start", "zoning", {"latitude": 12.0, "longitude": -34.0}
    )
    hass.states.async_set(
        "zone.synthetic_end", "zoning", {"latitude": 12.5, "longitude": -33.5}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic rejected profile",
        data={
            CONF_CALENDAR_ENTITY_IDS: ["calendar.synthetic_rejected"],
            CONF_START_ANCHOR_ENTITY_ID: "zone.synthetic_start",
            CONF_END_ANCHOR_ENTITY_ID: "zone.synthetic_end",
            CONF_PHYSICAL_EVENT_POLICY: "include",
            CONF_ONLINE_EVENT_POLICY: "exclude",
            CONF_ALL_DAY_EVENT_POLICY: "exclude",
            CONF_NO_LOCATION_EVENT_POLICY: "exclude",
            CONF_ROUTE_PROVIDER: "openrouteservice_hosted",
            CONF_ROUTE_PROVIDER_API_KEY: private_key,
            CONF_LOCATION_DATA_CONSENT: "accepted",
            CONF_MAX_GEOCODE_REQUESTS_PER_REFRESH: 1,
            CONF_MAX_ROUTE_REQUESTS_PER_REFRESH: 1,
            CONF_MAX_REQUEST_ATTEMPTS: 1,
            CONF_REQUEST_TIMEOUT_SECONDS: 10,
            CONF_GEOCODE_CACHE_RETENTION_HOURS: 24,
            CONF_ROUTE_CACHE_FRESH_HOURS: 6,
            CONF_ROUTE_CACHE_STALE_HOURS: 24,
            CONF_TOLL_POLICY: "avoid",
            CONF_HIGHWAY_POLICY: "allow",
            CONF_MINIMUM_HISTORY_SAMPLES: 5,
            CONF_MINIMUM_CORRECTION_PERCENT: 60,
            CONF_MAXIMUM_CORRECTION_PERCENT: 180,
            CONF_COLD_START_P90_PERCENT: 125,
        },
        version=1,
        minor_version=6,
    )
    entry.add_to_hass(hass)

    with patch.object(
        HomeAssistantCalendarSource,
        "async_read",
        synthetic_calendar_read,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_forecast_distance"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN
        assert state.attributes["quality"] in {"partial", "unavailable"}
        assert aioclient_mock.call_count == 1
        request_method, request_url, _, request_headers = aioclient_mock.mock_calls[0]
        assert request_method == "GET"
        assert str(request_url.with_query(None)) == ORS_HOSTED_GEOCODING_ENDPOINT
        assert request_url.query["api_key"] == private_key
        assert "Authorization" not in request_headers
        for private_value in (private_location, private_key, provider_echo):
            assert private_value not in repr(state)
            assert private_value not in caplog.text

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
