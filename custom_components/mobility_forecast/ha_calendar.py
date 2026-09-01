"""Read-only Home Assistant calendar entity normalization boundary.

The adapter depends only on the small structural surface exposed by Home
Assistant's CalendarEntity and EntityComponent contracts. It does not log or
retain events beyond returning validated domain values, and it has no calendar
write, service, network, vehicle, or notification capability.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol, cast

from .domain.models import SourceEvent

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CONF_CALENDAR_ENTITY_IDS = "calendar_entity_ids"
_CALENDAR_ENTITY_ID = re.compile(r"calendar\.[a-z0-9_]+\Z")


class CalendarSourceUnavailable(RuntimeError):
    """Fail-closed source error carrying only a stable non-private reason."""


class CalendarEventContract(Protocol):
    """Read-only CalendarEvent fields used by normalization."""

    start: date | datetime
    end: date | datetime
    summary: str
    description: str | None
    location: str | None
    uid: str | None
    recurrence_id: str | None

    @property
    def all_day(self) -> bool: ...

    @property
    def start_datetime_local(self) -> datetime: ...

    @property
    def end_datetime_local(self) -> datetime: ...


class CalendarEntityContract(Protocol):
    """Read-only CalendarEntity operation used by the source."""

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> Sequence[CalendarEventContract]: ...


class CalendarComponentContract(Protocol):
    """EntityComponent lookup surface used by the source."""

    def get_entity(self, entity_id: str) -> CalendarEntityContract | None: ...


OnlineEventClassifier = Callable[[CalendarEventContract], bool]


@dataclass(frozen=True, slots=True)
class CalendarSourceConfig:
    """Explicit ordered calendar selection for one config entry."""

    entity_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.entity_ids:
            raise ValueError("at least one calendar entity is required")
        if any(
            entity_id != entity_id.strip()
            or _CALENDAR_ENTITY_ID.fullmatch(entity_id) is None
            for entity_id in self.entity_ids
        ):
            raise ValueError("calendar entity identifiers must use the calendar domain")
        if len(set(self.entity_ids)) != len(self.entity_ids):
            raise ValueError("calendar entity identifiers must be unique")

    @classmethod
    def from_entry_data(cls, data: Mapping[str, object]) -> CalendarSourceConfig:
        """Decode the versioned config-entry field without adding a fallback."""

        raw_entity_ids = data.get(CONF_CALENDAR_ENTITY_IDS)
        if not isinstance(raw_entity_ids, list):
            raise ValueError("calendar entity configuration is unavailable")
        entity_ids: list[str] = []
        for entity_id in cast(list[object], raw_entity_ids):
            if not isinstance(entity_id, str):
                raise ValueError("calendar entity configuration is unavailable")
            entity_ids.append(entity_id)
        return cls(tuple(entity_ids))


@dataclass(frozen=True, slots=True)
class HomeAssistantCalendarSource:
    """Normalize configured CalendarEntity reads into domain SourceEvents.

    Online-event classification is an explicit injected policy because Home
    Assistant's CalendarEvent contract has no provider-neutral online flag.
    """

    hass: HomeAssistant
    component: CalendarComponentContract
    config: CalendarSourceConfig
    classify_online: OnlineEventClassifier

    async def async_read(
        self, starts_at: datetime, ends_at: datetime
    ) -> tuple[SourceEvent, ...]:
        """Read one explicit aware window from every configured calendar."""

        _validate_window(starts_at, ends_at)
        normalized: list[SourceEvent] = []
        for entity_id in self.config.entity_ids:
            entity = self.component.get_entity(entity_id)
            if entity is None:
                raise CalendarSourceUnavailable("calendar_entity_unavailable")
            try:
                events = await entity.async_get_events(self.hass, starts_at, ends_at)
            except Exception:
                raise CalendarSourceUnavailable("calendar_read_failed") from None
            for event in events:
                try:
                    normalized.append(self._normalize(entity_id, event))
                except CalendarSourceUnavailable:
                    raise
                except Exception:
                    raise CalendarSourceUnavailable("calendar_event_invalid") from None
        return tuple(normalized)

    def _normalize(self, entity_id: str, event: CalendarEventContract) -> SourceEvent:
        uid = _non_empty_identifier(event.uid)
        if uid is None:
            raise CalendarSourceUnavailable("calendar_event_identifier_unavailable")
        recurrence_id = _non_empty_identifier(event.recurrence_id)
        event_id = uid if recurrence_id is None else f"{len(uid)}:{uid}{recurrence_id}"
        return SourceEvent(
            source_id=entity_id,
            event_id=event_id,
            starts_at=event.start_datetime_local,
            ends_at=event.end_datetime_local,
            all_day=event.all_day,
            is_online=self.classify_online(event),
            summary=event.summary,
            description=event.description,
            location_text=event.location,
        )


def validate_calendar_entity_ids(value: object) -> list[str]:
    """Voluptuous-compatible validator returning JSON-safe config-entry data."""

    if not isinstance(value, list):
        raise ValueError("select at least one calendar entity")
    entity_ids: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise ValueError("select at least one calendar entity")
        entity_ids.append(item)
    config = CalendarSourceConfig(tuple(entity_ids))
    return list(config.entity_ids)


def _validate_window(starts_at: datetime, ends_at: datetime) -> None:
    if (
        starts_at.tzinfo is None
        or starts_at.utcoffset() is None
        or ends_at.tzinfo is None
        or ends_at.utcoffset() is None
    ):
        raise ValueError("calendar source window must be timezone-aware")
    if ends_at <= starts_at:
        raise ValueError("calendar source window end must be after start")


def _non_empty_identifier(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value
