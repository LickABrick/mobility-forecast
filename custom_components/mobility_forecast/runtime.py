"""Typed composition root for one Home Assistant forecast profile.

Runtime data keeps Home Assistant adapters entry-scoped while exposing only the
specific read-only boundaries each adapter needs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol, cast

from .calendar_profile_source import CalendarIngestionProfileSource
from .coordinator import ProfileCoordinator
from .diagnostics import DiagnosticsSnapshot
from .ha_calendar import (
    CalendarSourceConfig,
    HomeAssistantCalendarSource,
    classify_online_event,
)
from .ha_zone_anchors import HomeAssistantZoneAnchorResolver
from .profile_config import ProfilePlanningConfig

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


def build_runtime(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> ProfileRuntimeData:
    """Build an isolated calendar-reading runtime for one config entry."""

    from homeassistant.components.calendar.const import DATA_COMPONENT
    from homeassistant.util import dt as dt_util

    from .ha_storage import HomeAssistantProfileStorage

    config_entry_id = entry.entry_id
    planning_config = ProfilePlanningConfig.from_entry_data(entry.data)
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
    return ProfileRuntimeData(
        coordinator=ProfileCoordinator(
            config_entry_id,
            source=CalendarIngestionProfileSource(
                calendar_source=calendar_source,
                zone_anchor_resolver=zone_anchor_resolver,
                event_filter_policy=planning_config.event_filter_policy,
                now=dt_util.now,
                horizon=CALENDAR_HORIZON,
            ),
            storage=HomeAssistantProfileStorage(hass, config_entry_id),
        ),
        diagnostics_source=_PendingDiagnosticsSource(),
    )
