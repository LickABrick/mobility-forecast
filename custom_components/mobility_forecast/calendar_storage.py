"""Privacy-safe complete distance overlays; detailed stops remain runtime-only."""

import hashlib
import json
import math
import re
from datetime import UTC, date, datetime, timedelta

from .locations import home_and_known
from .routing import Plan

TTL = 7200
RETENTION = 24 * 3600


def routing_identity(hass, options):
    home, _ = home_and_known(hass, options.get("known_locations", {}))
    value = {
        key: options.get(key)
        for key in ("routing", "region", "ignore_nested_appointments")
    }
    value["calendars"] = sorted(options.get("calendars", []))
    value["known_locations"] = options.get("known_locations", {})
    value["home"] = home.identifier
    value["timezone"] = hass.config.time_zone
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def restore(payload, identity, now):
    result = {}
    if not isinstance(payload, dict):
        return result
    for key, row in list(payload.items())[:31]:
        try:
            day = date.fromisoformat(key)
            verified = datetime.fromisoformat(row["verified_at"])
            routed = datetime.fromisoformat(row["routed_at"])
            distance = row["distance_km"]
            fingerprint = row["fingerprint"]
            if (
                row["schema"] != 1
                or row["complete"] is not True
                or row["routing_identity"] != identity
                or isinstance(distance, bool)
                or not isinstance(distance, (int, float))
                or not math.isfinite(distance)
                or distance < 0
                or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
                or not now.date() <= day <= now.date() + timedelta(days=30)
                or verified.tzinfo is None
                or routed.tzinfo is None
                or not 0
                <= (now.astimezone(UTC) - verified.astimezone(UTC)).total_seconds()
                <= RETENTION
                or routed > verified
                or (now.astimezone(UTC) - routed.astimezone(UTC)).total_seconds()
                > 7 * 86400
            ):
                continue
            result[day] = (Plan(float(distance), True), fingerprint, verified, routed)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return result


def serialize(runtime):
    identity = routing_identity(runtime.hass, runtime.entry.options)
    return {
        day.isoformat(): {
            "schema": 1,
            "complete": True,
            "distance_km": plan.distance_km,
            "fingerprint": runtime.day_fingerprints[day],
            "verified_at": runtime.day_verified[day].isoformat(),
            "routed_at": runtime.day_routed[day].isoformat(),
            "routing_identity": identity,
        }
        for day, plan in sorted(runtime.plans.items())
        if plan.complete
        and day in runtime.day_fingerprints
        and day in runtime.day_verified
        and day in runtime.day_routed
    }
