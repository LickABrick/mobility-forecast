"""Conservative physical location recognition; no implicit geocoding."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    identifier: str
    query: str
    source: str


def normalize(text: str | None, known: dict[str, str] | None = None) -> Location | None:
    if not text:
        return None
    clean = " ".join(text.strip().split())
    key = clean.casefold().strip(" ,")
    if re.search(r"https?://|zoom\.|teams\.|meet\.google|online|webinar", key):
        return None
    mapping = {k.casefold(): v for k, v in (known or {}).items()}
    if key in mapping:
        resolved = normalize(mapping[key])
        return resolved
    coordinate = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", clean)
    if coordinate:
        lat, lon = map(float, coordinate.groups())
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            query = f"{lat:.5f},{lon:.5f}"
            return Location(query, query, "coordinates")
        return None
    # Require a street number and locality separator, not arbitrary venue names.
    if re.search(r"\d", clean) and "," in clean and re.search(r"[a-zA-Z]{3}", clean):
        return Location(key, clean, "address")
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
