"""Deterministic, synthetic-only composition harness for contract smoke tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import cast

from custom_components.mobility_forecast.coordinator import ProfileUpdate
from custom_components.mobility_forecast.domain import (
    EventFilterPolicy,
    ForecastPolicy,
    ItineraryCandidate,
    ResolvedLocation,
    RouteOptions,
    RouteProvider,
    append_plan_revision,
    assemble_plan_revision,
    build_distance_forecast,
    classify_event,
)
from custom_components.mobility_forecast.ha_calendar import (
    CalendarEventContract,
    HomeAssistantCalendarSource,
)
from custom_components.mobility_forecast.storage import ProfileState


@dataclass(frozen=True, slots=True)
class SyntheticCalendarEvent:
    """Minimal synthetic CalendarEvent contract with deterministic UTC dates."""

    start: date | datetime
    end: date | datetime
    summary: str
    description: str | None = None
    location: str | None = None
    uid: str | None = None
    recurrence_id: str | None = None

    @property
    def all_day(self) -> bool:
        return not isinstance(self.start, datetime)

    @property
    def start_datetime_local(self) -> datetime:
        if isinstance(self.start, datetime):
            return self.start
        return datetime.combine(self.start, time.min, tzinfo=UTC)

    @property
    def end_datetime_local(self) -> datetime:
        if isinstance(self.end, datetime):
            return self.end
        return datetime.combine(self.end, time.min, tzinfo=UTC)


class SyntheticCalendarEntity:
    """In-memory read-only calendar entity; it has no external access path."""

    def __init__(self, events: Sequence[SyntheticCalendarEvent]) -> None:
        self._events = tuple(events)
        self.calls: list[tuple[object, datetime, datetime]] = []

    async def async_get_events(
        self, hass: object, start_date: datetime, end_date: datetime
    ) -> Sequence[CalendarEventContract]:
        self.calls.append((hass, start_date, end_date))
        return cast(Sequence[CalendarEventContract], self._events)


class SyntheticCalendarComponent:
    """Exact in-memory entity lookup used by the calendar adapter."""

    def __init__(self, entities: Mapping[str, SyntheticCalendarEntity]) -> None:
        self._entities = dict(entities)
        self.lookups: list[str] = []

    def get_entity(self, entity_id: str) -> SyntheticCalendarEntity | None:
        self.lookups.append(entity_id)
        return self._entities.get(entity_id)


class SyntheticProfileStorage:
    """Entry-scoped in-memory storage fake recording coordinator transactions."""

    def __init__(self, states: Mapping[str, ProfileState]) -> None:
        self.states = dict(states)
        self.loads: list[str] = []
        self.saves: list[tuple[str, ProfileState]] = []

    async def load(self, config_entry_id: str) -> ProfileState:
        self.loads.append(config_entry_id)
        return self.states[config_entry_id]

    async def save(self, config_entry_id: str, state: ProfileState) -> None:
        self.saves.append((config_entry_id, state))
        self.states[config_entry_id] = state


@dataclass(frozen=True, slots=True)
class SyntheticPipelineProfileSource:
    """Compose existing contracts with only explicit deterministic fixture inputs.

    This harness is intentionally test-only. It proves contract compatibility but
    does not choose production windows, identifiers, location resolution, routing,
    refresh cadence, or policy defaults.
    """

    calendar_source: HomeAssistantCalendarSource
    window_start: datetime
    window_end: datetime
    generated_at: datetime
    revision_id: str
    filter_policy: EventFilterPolicy
    initial_origin: ResolvedLocation
    destinations: Mapping[str, ResolvedLocation]
    route_options: RouteOptions
    route_provider: RouteProvider
    forecast_policy: ForecastPolicy

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        events = await self.calendar_source.async_read(
            self.window_start, self.window_end
        )
        candidates: list[ItineraryCandidate] = []
        for event in events:
            if not classify_event(event, self.filter_policy).included:
                continue
            destination = (
                self.destinations.get(event.location_text)
                if event.location_text is not None
                else None
            )
            candidates.append(
                ItineraryCandidate(
                    event=event,
                    deduplication_key=f"{len(event.source_id)}:{event.source_id}{event.event_id}",
                    destination=destination,
                    destination_reason=(
                        "primary_accepted"
                        if destination is not None
                        else "primary_missing"
                    ),
                )
            )

        revision = await assemble_plan_revision(
            revision_id=self.revision_id,
            service_date=self.window_start.date(),
            created_at=self.generated_at,
            source_observed_at=self.generated_at,
            candidates=tuple(candidates),
            initial_origin=self.initial_origin,
            route_options=self.route_options,
            route_provider=self.route_provider,
        )
        next_state = ProfileState(
            revisions=append_plan_revision(previous_state.revisions, revision),
            pending_days=previous_state.pending_days,
            actuals=previous_state.actuals,
        )
        forecast = build_distance_forecast(
            revision, previous_state.actuals, self.forecast_policy
        )
        return ProfileUpdate(
            state=next_state,
            forecasts=(forecast,),
            generated_at=self.generated_at,
        )
