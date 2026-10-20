"""PDOK address-only matching. Conservative NL-only exact-number validation."""

import re

from .providers import cache_key

URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"


def coordinates(query):
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", query)
    if match:
        lat, lon = map(float, match.groups())
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None


def parse_address(payload, query):
    docs = payload.get("response", {}).get("docs", [])
    # Require an explicit house number plus Dutch postcode, not a centroid or
    # guessed country. This intentionally rejects less-specific destinations.
    postcode = re.search(r"\b([1-9]\d{3})\s*([A-Za-z]{2})\b", query)
    if not postcode:
        return None
    expected = "".join(postcode.groups()).upper()
    prefix = query[: postcode.start()] + query[postcode.end() :]
    numbers = re.findall(r"\b\d+[A-Za-z]?\b", prefix)
    if not numbers:
        return None
    results = set()
    for doc in docs[:3]:
        house = str(doc.get("huisnummer", "")) + str(doc.get("huisletter", ""))
        if (
            doc.get("type") != "adres"
            or str(doc.get("postcode", "")).replace(" ", "").upper() != expected
            or house.casefold() != numbers[-1].casefold()
        ):
            continue
        match = re.fullmatch(
            r"POINT\(([-\d.]+) ([-\d.]+)\)", doc.get("centroide_ll", "")
        )
        if match:
            lon, lat = map(float, match.groups())
            if 50 <= lat <= 54 and 3 <= lon <= 8:
                results.add((lat, lon))
    return next(iter(results)) if len(results) == 1 else None


async def resolve(http, query):
    direct = coordinates(query)
    if direct:
        return direct, "coordinates"
    if not re.search(r"\b[1-9]\d{3}\s*[A-Za-z]{2}\b", query) or re.search(
        r"\b(germany|belgium|belgië|duitsland|france|frankrijk)\b", query, re.I
    ):
        return None, "geocoding_unsupported_region"
    params = {
        "q": query,
        "fq": "type:adres",
        "rows": 3,
        "fl": "type,postcode,huisnummer,huisletter,centroide_ll",
    }
    key = cache_key(URL, params)
    value = await http.get(URL, params, 30 * 86400)
    if isinstance(value, dict) and "resolved" in value:
        return (tuple(value["resolved"]) if value["resolved"] else None), value[
            "status"
        ]
    result = parse_address(value, query)
    status = "resolved" if result else "geocoding_ambiguous"
    http.put(
        key, {"resolved": result, "status": status}, 30 * 86400 if result else 86400
    )
    return result, status
