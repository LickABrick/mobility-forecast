"""Source compatibility and finite distance normalization."""

import math
from typing import Any


class InvalidReading(ValueError):
    """Reading cannot safely be used."""


def kilometers(value: Any, unit: str | None) -> float:
    if unit not in ("km", "mi"):
        raise InvalidReading("unit")
    try:
        number = float(value)
    except (ValueError, TypeError) as err:
        raise InvalidReading("value") from err
    if not math.isfinite(number) or number < 0:
        raise InvalidReading("value")
    return number * (1.609344 if unit == "mi" else 1)


def validate_source(state: Any) -> float:
    if state is None:
        raise InvalidReading("missing")
    attrs = state.attributes
    name = (state.entity_id + " " + attrs.get("friendly_name", "")).lower()
    if any(
        word in name
        for word in (
            "range",
            "trip",
            "remaining",
            "actieradius",
            "dagteller",
            "walking",
            "running",
            "daily",
            "weekly",
            "today",
            "vandaag",
            "steps",
            "activity",
            "wandel",
            "hardloop",
        )
    ):
        raise InvalidReading("not_odometer")
    if attrs.get("last_reset") is not None:
        raise InvalidReading("resetting_counter")
    cumulative = attrs.get("state_class") in ("total", "total_increasing")
    named = any(word in name for word in ("odometer", "mileage", "kilometerstand"))
    if not (cumulative or named):
        raise InvalidReading("not_odometer")
    if attrs.get("device_class") not in (None, "distance"):
        raise InvalidReading("not_odometer")
    return kilometers(state.state, attrs.get("unit_of_measurement"))
