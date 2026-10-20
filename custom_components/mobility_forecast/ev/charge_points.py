"""NDW GeoJSON adapter. Fail closed on undocumented/inconsistent power units."""

import math
from dataclasses import asdict
from datetime import datetime

from .energy import number
from .models import ChargePoint
from .providers import ProviderError, cache_key

URL = "https://dotnl.ndw.nu/api/rest/geojson/dynamic-road-status/charge-point-data/v1/features"


def distance_m(lat, lon, other_lat, other_lon):
    a, b = map(math.radians, (lat, other_lat))
    dlat = b - a
    dlon = math.radians(other_lon - lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def parse_points(payload, lat, lon, radius, now):
    if (
        not isinstance(payload, dict)
        or payload.get("type") != "FeatureCollection"
        or not isinstance(payload.get("features"), list)
        or len(payload["features"]) > 1000
    ):
        raise ProviderError("charger_schema_invalid")
    points = []
    for feature in payload["features"]:
        try:
            geometry = feature["geometry"]
            if geometry["type"] != "Point":
                continue
            lng, latitude = geometry["coordinates"]
            number(latitude, -90, 90)
            number(lng, -180, 180)
            separation = distance_m(lat, lon, latitude, lng)
            props = feature["properties"]
            if separation > radius or props.get("open") is not True:
                continue
            updated = datetime.fromisoformat(props["last_updated"])
            if (
                updated.tzinfo is None
                or not 0 <= (now - updated).total_seconds() <= 86400
            ):
                continue
            for connector in props.get("availabilities") or []:
                if not isinstance(connector, dict):
                    continue
                if (
                    connector.get("connector_type") != "IEC_62196_T2"
                    or connector.get("power_type") not in ("AC1", "AC2", "AC3")
                    or connector.get("total", 0) <= 0
                ):
                    continue
                # Published schema says kW. Live endpoint observed 15000 for an
                # AC connector: ambiguous units are NOT silently reinterpreted.
                try:
                    power = number(connector["power_max"], 0.1, 43)
                except (KeyError, ValueError, TypeError):
                    continue
                status = (
                    "unknown"
                    if (now - updated).total_seconds() > 300
                    else "available"
                    if connector.get("available", 0) > 0
                    else "occupied"
                )
                points.append(
                    ChargePoint(
                        str(feature["id"])[:128],
                        latitude,
                        lng,
                        power,
                        separation,
                        status,
                        updated_at=updated.isoformat(),
                    )
                )
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return sorted(points, key=lambda p: (p.distance_m, -p.ac_power_kw, p.provider_id))[
        :3
    ]


async def discover(http, lat, lon, radius, now):
    delta = radius / 111000
    lng_delta = delta / max(0.1, math.cos(math.radians(lat)))
    params = {
        "bbox": f"{lon - lng_delta},{lat - delta},{lon + lng_delta},{lat + delta}"
    }
    key = cache_key(URL, params)
    payload = await http.get(URL, params, 86400)
    if isinstance(payload, dict) and "validated_points" in payload:
        return [
            ChargePoint(**{**p, "status": "unknown"})
            for p in payload["validated_points"]
        ]
    points = parse_points(payload, lat, lon, radius, now)
    http.put(key, {"validated_points": [asdict(p) for p in points]}, 86400)
    return points
