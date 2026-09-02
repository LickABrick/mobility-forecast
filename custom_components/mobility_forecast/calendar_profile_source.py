"""Privacy-bounded calendar ingestion for one forecast profile.

This production source reads the explicitly selected Home Assistant calendars
inside one bounded future window and publishes only unavailable distance forecasts
for dates that contain events. Event content is not persisted or projected.
Configured anchors and structural filters remain unconsumed until endpoint and
routing adapters are composed; distance stays unknown rather than becoming zero.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from .coordinator import ProfileUpdate
from .domain.models import DataQuality, Forecast
from .ha_calendar import HomeAssistantCalendarSource
from .storage import ProfileState


@dataclass(frozen=True, slots=True)
class CalendarIngestionProfileSource:
    """Read a bounded calendar window without retaining private event content."""

    calendar_source: HomeAssistantCalendarSource
    now: Callable[[], datetime]
    horizon: timedelta

    def __post_init__(self) -> None:
        if self.horizon <= timedelta(0):
            raise ValueError("calendar horizon must be positive")

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        """Return date-only unavailable forecasts until planning is configured."""

        generated_at = self.now()
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("calendar source clock must be timezone-aware")
        events = await self.calendar_source.async_read(
            generated_at, generated_at + self.horizon
        )
        service_dates = tuple(sorted({event.starts_at.date() for event in events}))
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
