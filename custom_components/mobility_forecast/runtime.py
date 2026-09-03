"""Typed composition root for one Home Assistant forecast profile.

Runtime data keeps Home Assistant adapters entry-scoped while exposing only the
specific read-only boundaries each adapter needs.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol, cast

from .coordinator import ProfileCoordinator
from .diagnostics import DiagnosticsSnapshot
from .forecast_config import ProfileForecastConfig
from .ha_calendar import (
    CalendarSourceConfig,
    HomeAssistantCalendarSource,
    classify_online_event,
)
from .ha_zone_anchors import HomeAssistantZoneAnchorResolver
from .openrouteservice import OpenRouteServiceAdapters, build_openrouteservice_adapters
from .openrouteservice_http import (
    OpenRouteServiceHttpGeocodeTransport,
    OpenRouteServiceHttpRouteTransport,
)
from .profile_config import ProfilePlanningConfig
from .route_provider_config import ProfileRouteConfig
from .routed_profile_source import RoutedCalendarProfileSource

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .ha_calendar import CalendarComponentContract


CALENDAR_HORIZON = timedelta(days=7)
REFRESH_INTERVAL = timedelta(minutes=15)


class DiagnosticsSource(Protocol):
    """Build one current aggregate snapshot without exposing private raw state."""

    async def read(self) -> DiagnosticsSnapshot:
        """Return the versioned diagnostics input for this profile."""
        ...


@dataclass(slots=True)
class ProfileRuntimeData:
    """Entry-scoped read-only boundaries shared by Home Assistant adapters."""

    coordinator: ProfileCoordinator
    diagnostics_source: DiagnosticsSource
    _remove_interval: Callable[[], None] | None = None

    async def async_refresh(self) -> None:
        """Refresh once while keeping source errors inside the read-only runtime."""

        try:
            await self.coordinator.refresh()
        except Exception:
            # Adapter errors contain only stable reason codes. The coordinator
            # marks the failed attempt and entities are notified as unavailable.
            return

    def start(self, hass: HomeAssistant) -> None:
        """Schedule bounded periodic reads for this loaded config entry."""

        from homeassistant.helpers.event import async_track_time_interval

        if self._remove_interval is not None:
            raise RuntimeError("profile runtime is already started")

        async def refresh_at_interval(now: object) -> None:
            del now
            await self.async_refresh()

        self._remove_interval = async_track_time_interval(
            hass, refresh_at_interval, REFRESH_INTERVAL
        )

    def stop(self) -> None:
        """Cancel periodic reads without touching calendars or persisted state."""

        if self._remove_interval is not None:
            self._remove_interval()
            self._remove_interval = None


class _PendingDiagnosticsSource:
    """Avoid fabricating diagnostics before aggregate source composition exists."""

    async def read(self) -> DiagnosticsSnapshot:
        raise RuntimeError("profile diagnostics source is not configured")


async def build_runtime(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> ProfileRuntimeData:
    """Build an isolated real routed-forecast runtime for one config entry."""

    from homeassistant.components.calendar.const import DATA_COMPONENT
    from homeassistant.util import dt as dt_util

    from .ha_http import build_home_assistant_http_sender
    from .ha_provider_cache import HomeAssistantProviderCaches
    from .ha_storage import HomeAssistantProfileStorage

    config_entry_id = entry.entry_id
    planning_config = ProfilePlanningConfig.from_entry_data(entry.data)
    route_config = ProfileRouteConfig.from_entry_data(entry.data)
    forecast_config = ProfileForecastConfig.from_entry_data(entry.data)
    component = cast("CalendarComponentContract", hass.data[DATA_COMPONENT])
    calendar_source = HomeAssistantCalendarSource(
        hass=hass,
        component=component,
        config=CalendarSourceConfig.from_entry_data(entry.data),
        classify_online=classify_online_event,
    )
    zone_anchor_resolver = HomeAssistantZoneAnchorResolver(
        hass.states,
        planning_config,
    )
    provider_caches = HomeAssistantProviderCaches(hass, config_entry_id)
    initialized_at = dt_util.now()
    await provider_caches.async_initialize(
        evaluated_at=initialized_at,
        maximum_geocode_age=route_config.geocode_cache_policy.maximum_age,
        maximum_route_age=route_config.route_cache_policy.maximum_stale_age,
    )
    sender = build_home_assistant_http_sender(hass)

    def build_adapters() -> OpenRouteServiceAdapters:
        return build_openrouteservice_adapters(
            config=route_config,
            geocode_transport=OpenRouteServiceHttpGeocodeTransport(
                sender=sender, now=dt_util.now
            ),
            route_transport=OpenRouteServiceHttpRouteTransport(
                sender=sender, now=dt_util.now
            ),
            geocode_cache=provider_caches.geocode_cache,
            route_cache=provider_caches.route_cache,
            privacy_key=provider_caches.privacy_key,
            now=dt_util.now,
        )

    return ProfileRuntimeData(
        coordinator=ProfileCoordinator(
            config_entry_id,
            source=RoutedCalendarProfileSource(
                calendar_source=calendar_source,
                zone_anchor_resolver=zone_anchor_resolver,
                event_filter_policy=planning_config.event_filter_policy,
                route_options=route_config.route_options,
                forecast_policy=forecast_config.forecast_policy,
                build_provider_adapters=build_adapters,
                new_revision_id=lambda: f"revision:{secrets.token_hex(16)}",
                now=dt_util.now,
                horizon=CALENDAR_HORIZON,
            ),
            storage=HomeAssistantProfileStorage(hass, config_entry_id),
        ),
        diagnostics_source=_PendingDiagnosticsSource(),
    )
