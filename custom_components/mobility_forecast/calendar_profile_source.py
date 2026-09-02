"""Privacy-bounded calendar ingestion for one forecast profile.

This production source reads the explicitly selected Home Assistant calendars
inside one bounded future window, applies the profile's explicit structural filter,
and publishes only unavailable distance forecasts for included service dates. Event
content is not persisted or projected. Configured zone anchors are resolved as a
fail-closed prerequisite. Event destinations and routing remain uncomposed, so
distance stays unknown rather than becoming zero.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from .coordinator import ProfileUpdate
from .domain.calendar_filters import EventFilterPolicy, classify_event
from .domain.models import DataQuality, Forecast
from .ha_calendar import HomeAssistantCalendarSource
from .ha_zone_anchors import ZoneAnchorResolver
from .storage import ProfileState


@dataclass(frozen=True, slots=True)
class CalendarIngestionProfileSource:
    """Read a bounded calendar window without retaining private event content."""

    calendar_source: HomeAssistantCalendarSource
    zone_anchor_resolver: ZoneAnchorResolver
    event_filter_policy: EventFilterPolicy
    now: Callable[[], datetime]
    horizon: timedelta

    def __post_init__(self) -> None:
        if self.horizon <= timedelta(0):
            raise ValueError("calendar horizon must be positive")

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        """Return filtered date-only forecasts until route planning is composed."""

        generated_at = self.now()
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("calendar source clock must be timezone-aware")
        # Both explicit anchors must currently resolve before this refresh can
        # publish. Failures propagate to the coordinator, keeping the entity
        # unavailable without persisting coordinates or fabricating distance.
        self.zone_anchor_resolver.resolve()
        events = await self.calendar_source.async_read(
            generated_at, generated_at + self.horizon
        )
        service_dates = tuple(
            sorted(
                {
                    event.starts_at.date()
                    for event in events
                    if classify_event(event, self.event_filter_policy).included
                }
            )
        )
        forecasts = tuple(
            Forecast(
                service_date=service_date,
                distance_p50_m=None,
                distance_p90_m=None,
                required_soc_p50_percent=None,
                required_soc_p90_percent=None,
                quality=DataQuality.UNAVAILABLE,
                reason_codes=("forecast_pipeline_unconfigured",),
            )
            for service_date in service_dates
        )
        return ProfileUpdate(
            state=previous_state,
            forecasts=forecasts,
            generated_at=generated_at,
        )
