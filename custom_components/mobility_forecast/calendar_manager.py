"""Bounded native calendar retrieval and privacy-minimal normalization."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, time

from .locations import Location, normalize


@dataclass(frozen=True)
class Appointment:
    start: datetime
    end: datetime
    location: Location | None
    all_day: bool
    identifier: str


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
            if end <= start or row.get("status") == "cancelled":
                continue
            location = normalize(row.get("location"), known)
            fingerprint = hashlib.sha256(
                f"{start.isoformat()}|{end.isoformat()}|{location.identifier if location else ''}".encode()
            ).hexdigest()
            unique[fingerprint] = Appointment(
                start, end, location, all_day, fingerprint
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
        raise ValueError("Incomplete calendar response")
    rows = [
        event for entity in entities for event in response[entity].get("events", [])
    ]
    return [
        event
        for event in normalize_events(rows, start.tzinfo, known)
        if event.end > start and event.start < end
    ]
