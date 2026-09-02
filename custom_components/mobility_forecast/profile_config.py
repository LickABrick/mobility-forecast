"""Versioned, privacy-conscious profile planning configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .domain.calendar_filters import EventFilterPolicy

CONF_START_ANCHOR_ENTITY_ID = "start_anchor_entity_id"
CONF_END_ANCHOR_ENTITY_ID = "end_anchor_entity_id"
CONF_PHYSICAL_EVENT_POLICY = "physical_event_policy"
CONF_ONLINE_EVENT_POLICY = "online_event_policy"
CONF_ALL_DAY_EVENT_POLICY = "all_day_event_policy"
CONF_NO_LOCATION_EVENT_POLICY = "no_location_event_policy"

_ZONE_ENTITY_ID = re.compile(r"zone\.[a-z0-9_]+\Z")


class EventHandling(StrEnum):
    """Explicit include/exclude choice for one structural event category."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass(frozen=True, slots=True)
class ProfilePlanningConfig:
    """Planning inputs owned by one profile.

    Anchor identifiers are operational configuration and are omitted from the
    representation so accidental logs do not expose the user's selected zones.
    """

    start_anchor_entity_id: str = field(repr=False)
    end_anchor_entity_id: str = field(repr=False)
    physical_events: EventHandling
    online_events: EventHandling
    all_day_events: EventHandling
    events_without_location: EventHandling

    def __post_init__(self) -> None:
        _validate_zone_entity_id(self.start_anchor_entity_id)
        _validate_zone_entity_id(self.end_anchor_entity_id)

    @classmethod
    def from_entry_data(cls, data: Mapping[str, object]) -> ProfilePlanningConfig:
        """Decode required schema fields without filling missing policy values."""

        return cls(
            start_anchor_entity_id=_required_zone(data, CONF_START_ANCHOR_ENTITY_ID),
            end_anchor_entity_id=_required_zone(data, CONF_END_ANCHOR_ENTITY_ID),
            physical_events=_required_handling(data, CONF_PHYSICAL_EVENT_POLICY),
            online_events=_required_handling(data, CONF_ONLINE_EVENT_POLICY),
            all_day_events=_required_handling(data, CONF_ALL_DAY_EVENT_POLICY),
            events_without_location=_required_handling(
                data, CONF_NO_LOCATION_EVENT_POLICY
            ),
        )

    def as_entry_data(self) -> dict[str, str]:
        """Return the exact JSON-safe config-entry representation."""

        return {
            CONF_START_ANCHOR_ENTITY_ID: self.start_anchor_entity_id,
            CONF_END_ANCHOR_ENTITY_ID: self.end_anchor_entity_id,
            CONF_PHYSICAL_EVENT_POLICY: self.physical_events.value,
            CONF_ONLINE_EVENT_POLICY: self.online_events.value,
            CONF_ALL_DAY_EVENT_POLICY: self.all_day_events.value,
            CONF_NO_LOCATION_EVENT_POLICY: self.events_without_location.value,
        }

    @property
    def event_filter_policy(self) -> EventFilterPolicy:
        """Project structural choices into the existing pure filter contract."""

        return EventFilterPolicy(
            include_terms=(),
            exclude_terms=(),
            allow_physical=self.physical_events is EventHandling.INCLUDE,
            allow_online=self.online_events is EventHandling.INCLUDE,
            allow_all_day=self.all_day_events is EventHandling.INCLUDE,
            require_location=self.events_without_location is EventHandling.EXCLUDE,
        )


def _required_zone(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is unavailable")
    _validate_zone_entity_id(value)
    return value


def _validate_zone_entity_id(value: str) -> None:
    if value != value.strip() or _ZONE_ENTITY_ID.fullmatch(value) is None:
        raise ValueError("anchor entity identifiers must use the zone domain")


def _required_handling(data: Mapping[str, object], key: str) -> EventHandling:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is unavailable")
    try:
        return EventHandling(value)
    except ValueError:
        raise ValueError(f"{key} is unavailable") from None
