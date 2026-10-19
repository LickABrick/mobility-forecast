"""Bounded native calendar retrieval and privacy-minimal normalization."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time

from .locations import Location, normalize


class EventBatch(list):
    """Normalized events with only aggregate retrieval metadata."""

    def __init__(self, events, retrieved_count):
        super().__init__(events)
        self.retrieved_count = retrieved_count


class CalendarResponseError(ValueError):
    """Calendar returned an invalid or incomplete response."""


@dataclass(frozen=True)
class Appointment:
    start: datetime
    end: datetime
    location: Location | None
    all_day: bool
    identifier: str
    virtual: bool = False


def parse_time(value, zone):
    if isinstance(value, dict):
        value = value.get("dateTime", value.get("date"))
    if len(value) == 10:
        return datetime.combine(
            datetime.fromisoformat(value).date(), time(), zone
        ), True
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return stamp.replace(tzinfo=zone) if stamp.tzinfo is None else stamp.astimezone(
        zone
    ), False


def normalize_events(rows, zone, known=None):
    unique = {}
    for row in rows:
        try:
            start, all_day = parse_time(row["start"], zone)
            end, _ = parse_time(row["end"], zone)
            if (
                end.astimezone(UTC) <= start.astimezone(UTC)
                or row.get("status") == "cancelled"
            ):
                continue
            location = normalize(row.get("location"), known)
            virtual = bool(
                re.search(
                    r"https?://|zoom\.|teams\.|meet\.google|online|webinar",
                    str(row.get("location", "")).casefold(),
                )
            )
            fingerprint = hashlib.sha256(
                f"{start.astimezone(UTC).isoformat()}|{end.astimezone(UTC).isoformat()}|{location.identifier if location else ''}|{virtual}".encode()
            ).hexdigest()
            unique[fingerprint] = Appointment(
                start,
                end,
                location,
                all_day,
                fingerprint,
                virtual,
            )
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return sorted(unique.values(), key=lambda e: e.start)


async def fetch_events(hass, entities, start, end, known=None):
    if not entities:
        return []
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entities,
            "start_date_time": start.isoformat(),
            "end_date_time": end.isoformat(),
        },
        blocking=True,
        return_response=True,
    )
    if not isinstance(response, dict) or any(
        entity not in response for entity in entities
    ):
        raise CalendarResponseError
    if any(
        not isinstance(response[entity], dict)
        or not isinstance(response[entity].get("events"), list)
        or any(not isinstance(event, dict) for event in response[entity]["events"])
        for entity in entities
    ):
        raise CalendarResponseError
    rows = [
        event for entity in entities for event in response[entity].get("events", [])
    ]
    for row in rows:
        try:
            parse_time(row["start"], start.tzinfo)
            parse_time(row["end"], start.tzinfo)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise CalendarResponseError from None
    return EventBatch(
        [
            event
            for event in normalize_events(rows, start.tzinfo, known)
            if event.end.astimezone(UTC) > start.astimezone(UTC)
            and event.start.astimezone(UTC) < end.astimezone(UTC)
        ],
        len(rows),
    )


def preprocess_appointments(events, ignore_nested=False):
    """Pure deterministic selection; compare instants, never titles or addresses.

    Only retained routable, same-local-day timed appointments suppress children.
    Overnight travel semantics remain conservative. Virtual events never route.
    """
    unique = {event.identifier: event for event in events if not event.virtual}
    ordered = sorted(
        unique.values(),
        key=lambda e: (
            e.start.astimezone(UTC),
            -e.end.astimezone(UTC).timestamp(),
            e.identifier,
        ),
    )
    selected = []
    ignored = 0
    for child in ordered:
        start, end = child.start.astimezone(UTC), child.end.astimezone(UTC)
        if (
            ignore_nested
            and not child.all_day
            and any(
                parent.location is not None
                and not parent.all_day
                and parent.start.date() == parent.end.date()
                and parent.start.astimezone(UTC) <= start
                and parent.end.astimezone(UTC) >= end
                and parent.end.astimezone(UTC) - parent.start.astimezone(UTC)
                > end - start
                for parent in selected
            )
        ):
            ignored += 1
        else:
            selected.append(child)
    return selected, ignored
