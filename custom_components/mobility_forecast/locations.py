"""Conservative physical location recognition; no implicit geocoding."""

import re
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Location:
    identifier: str
    query: str = field(compare=False)
    source: str = field(compare=False)
    legacy_identifier: str | None = field(default=None, compare=False)


def normalize(text: str | None, known: dict[str, str] | None = None) -> Location | None:
    if not text:
        return None
    clean = " ".join(text.strip().split())
    legacy = clean.casefold().strip(" ,")
    key = re.sub(r"\s*,\s*", ", ", legacy)
    if re.search(r"https?://|zoom\.|teams\.|meet\.google|online|webinar", key):
        return None
    mapping = {
        re.sub(r"\s*,\s*", ", ", " ".join(k.split()).casefold().strip(" ,")): v
        for k, v in (known or {}).items()
    }
    if key in mapping:
        resolved = normalize(mapping[key])
        return resolved
    coordinate = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", clean)
    if coordinate:
        lat, lon = map(Decimal, coordinate.groups())
        if -90 <= lat <= 90 and -180 <= lon <= 180:

            def exact(value):
                # Preserve the legacy five-decimal identity where exact, but
                # never round distinct higher-precision coordinates together.
                if value == 0:
                    value = Decimal(0)
                text = format(value, "f")
                if "." in text:
                    text = text.rstrip("0").rstrip(".")
                whole, _, fraction = text.partition(".")
                return whole + "." + fraction.ljust(5, "0")

            query = f"{exact(lat)},{exact(lon)}"
            return Location(query, query, "coordinates")
        return None
    # Require a street number and locality separator, not arbitrary venue names.
    if re.search(r"\d", clean) and "," in clean and re.search(r"[a-zA-Z]{3}", clean):
        return Location(key, clean, "address", legacy if legacy != key else None)
    return None


def home_and_known(hass, aliases=None):
    home = normalize(f"{hass.config.latitude},{hass.config.longitude}")
    known = {"home": home.query, "thuis": home.query}
    for state in hass.states.async_all("zone"):
        lat, lon = state.attributes.get("latitude"), state.attributes.get("longitude")
        if lat is not None and lon is not None:
            known[state.name] = f"{lat},{lon}"
            known[state.entity_id] = f"{lat},{lon}"
    known.update(aliases or {})
    return home, known
