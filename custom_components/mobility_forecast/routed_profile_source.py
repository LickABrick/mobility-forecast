"""Production calendar-to-route-to-forecast composition for one profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol

from .coordinator import ProfileUpdate
from .domain.actuals_forecasting import ForecastPolicy, build_distance_forecast
from .domain.calendar_filters import EventFilterPolicy, classify_event
from .domain.event_locations import (
    EventLocationFailure,
    EventLocationRequest,
    EventLocationResolver,
)
from .domain.location_resolution import LocationCandidate
from .domain.models import (
    DataQuality,
    Forecast,
    LocationProvenance,
    ResolvedLocation,
    SourceEvent,
)
from .domain.planning import (
    ItineraryCandidate,
    append_plan_revision,
    assemble_plan_revision,
)
from .domain.routing import RouteOptions, RouteProvider
from .ha_calendar import HomeAssistantCalendarSource
from .ha_zone_anchors import ZoneAnchorResolver
from .storage import ProfileState


class ProviderAdapters(Protocol):
    """One refresh-scoped geocoder/router pair with a fresh request budget."""

    @property
    def geocoder(self) -> EventLocationResolver:
        """Return the configured event-location resolver."""
        ...

    @property
    def router(self) -> RouteProvider:
        """Return the configured directional route provider."""
        ...


@dataclass(frozen=True, slots=True)
class RoutedCalendarProfileSource:
    """Build immutable routed revisions from real configured profile inputs."""

    calendar_source: HomeAssistantCalendarSource
    zone_anchor_resolver: ZoneAnchorResolver
    event_filter_policy: EventFilterPolicy
    route_options: RouteOptions
    forecast_policy: ForecastPolicy
    build_provider_adapters: Callable[[], ProviderAdapters]
    new_revision_id: Callable[[], str]
    now: Callable[[], datetime]
    horizon: timedelta

    def __post_init__(self) -> None:
        if self.horizon <= timedelta(0):
            raise ValueError("calendar horizon must be positive")

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        """Read, resolve and route included physical events by service date."""

        generated_at = self.now()
        _require_aware(generated_at)
        anchors = self.zone_anchor_resolver.resolve()
        events = await self.calendar_source.async_read(
            generated_at, generated_at + self.horizon
        )
        included = tuple(
            event
            for event in events
            if classify_event(event, self.event_filter_policy).included
            and not event.is_online
        )
        service_dates = tuple(sorted({event.starts_at.date() for event in included}))
        adapters = self.build_provider_adapters()
        revisions = previous_state.revisions
        forecasts: list[Forecast] = []
        for service_date in service_dates:
            candidates = await self._resolve_candidates(
                tuple(
                    event
                    for event in included
                    if event.starts_at.date() == service_date
                ),
                adapters.geocoder,
                anchors.end,
            )
            created_at = self.now()
            _require_aware(created_at)
            if revisions and created_at <= revisions[-1].created_at:
                created_at = revisions[-1].created_at + timedelta(microseconds=1)
            revision = await assemble_plan_revision(
                revision_id=self.new_revision_id(),
                service_date=service_date,
                created_at=created_at,
                source_observed_at=generated_at,
                candidates=candidates,
                initial_origin=anchors.start,
                route_options=self.route_options,
                route_provider=adapters.router,
            )
            revisions = append_plan_revision(revisions, revision)
            forecasts.append(
                build_distance_forecast(
                    revision, previous_state.actuals, self.forecast_policy
                )
            )
        return ProfileUpdate(
            state=ProfileState(
                revisions=revisions,
                pending_days=previous_state.pending_days,
                actuals=previous_state.actuals,
            ),
            forecasts=tuple(forecasts),
            generated_at=generated_at,
        )

    async def _resolve_candidates(
        self,
        events: tuple[SourceEvent, ...],
        resolver: EventLocationResolver,
        fallback: ResolvedLocation,
    ) -> tuple[ItineraryCandidate, ...]:
        candidates: list[ItineraryCandidate] = []
        fallback_location = replace(
            fallback,
            endpoint_id="anchor:end-fallback",
            provenance=LocationProvenance.CONFIGURED_FALLBACK,
            quality=DataQuality.PARTIAL,
        )
        for index, event in enumerate(events):
            destination: ResolvedLocation | None
            reason: str
            if event.location_text is None or not event.location_text.strip():
                destination = fallback_location
                reason = "configured_fallback"
            else:
                result = await resolver.resolve(
                    EventLocationRequest(event.location_text)
                )
                if isinstance(result, EventLocationFailure):
                    destination = None
                    reason = f"geocode_{result.category.value}"
                else:
                    candidate: LocationCandidate = result.as_candidate(f"event:{index}")
                    destination = candidate.as_resolved(DataQuality.COMPLETE)
                    reason = "primary_accepted"
            candidates.append(
                ItineraryCandidate(
                    event=event,
                    deduplication_key=(
                        f"{len(event.source_id)}:{event.source_id}{event.event_id}"
                    ),
                    destination=destination,
                    destination_reason=reason,
                )
            )
        return tuple(candidates)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("profile source clock must be timezone-aware")
