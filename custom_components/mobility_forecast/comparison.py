"""Frozen pre-day predictions and quality-aware comparisons, without backfilling."""

import math
from datetime import UTC, datetime, timedelta

RETENTION_DAYS = 365


def migrate_snapshots(snapshots):
    """Preserve legacy values without claiming verified capture times."""
    return {
        key: (
            {
                "schema": 1,
                "target_date": key,
                "predicted_km": value,
                "captured_at": None,
                "valid": False,
                "origin": "legacy",
                "calendar_included": None,
            }
            if isinstance(value, (int, float))
            else value
        )
        for key, value in snapshots.items()
    }


def capture(snapshots, forecast, now):
    """Only called by the 23:55 local schedule; never retrospectively."""
    target = now.date() + timedelta(days=1)
    if now.hour != 23 or now.minute != 55:
        return False
    day = next((d for d in forecast.days if d.day == target), None)
    if day is None or not math.isfinite(day.total_km):
        return False
    key = target.isoformat()
    if key in snapshots:
        return False
    snapshots[key] = {
        "schema": 1,
        "target_date": key,
        "predicted_km": day.total_km,
        "captured_at": now.isoformat(),
        "lead_seconds": (
            datetime.combine(target, datetime.min.time(), now.tzinfo).astimezone(UTC)
            - now.astimezone(UTC)
        ).total_seconds(),
        "quality": forecast.quality,
        "status": forecast.status.value,
        "calendar_included": day.planned_km is not None,
        "valid": forecast.status.value in ("ready", "provisional"),
        "origin": "scheduled",
    }
    return True


def comparisons(snapshots, history, now, days=365):
    indexed = {d.day: d for d in history}
    result = []
    for offset in range(days, 0, -1):
        target = now.date() - timedelta(days=offset)
        snapshot = snapshots.get(target.isoformat(), {})
        actual = indexed.get(target)
        quality = actual.quality if actual else "unknown"
        actual_km = (
            actual.km
            if actual
            and actual.coverage >= 0.9
            and quality in ("observed", "estimated")
            else None
        )
        prediction = snapshot.get("predicted_km") if snapshot.get("valid") else None
        difference = (
            actual_km - prediction
            if actual_km is not None and prediction is not None
            else None
        )
        result.append(
            {
                "date": target.isoformat(),
                "timestamp": datetime.combine(
                    target, datetime.min.time(), now.tzinfo
                ).isoformat(),
                "predicted_km": prediction,
                "actual_km": actual_km,
                "difference_km": difference,
                "absolute_error_km": abs(difference)
                if difference is not None
                else None,
                "relative_error_pct": 100 * difference / actual_km
                if difference is not None and actual_km
                else None,
                "captured_at": snapshot.get("captured_at"),
                "actual_quality": quality,
                "calendar_included": snapshot.get("calendar_included"),
                "eligible": prediction is not None
                and actual_km is not None
                and quality == "observed",
            }
        )
    return result


def metrics(records, days):
    rows = records[-days:]
    eligible = [r for r in rows if r["eligible"]]
    predicted = sum(r["predicted_km"] for r in eligible)
    actual = sum(r["actual_km"] for r in eligible)
    return {
        "days": days,
        "evaluated_days": len(eligible),
        "mae_km": sum(r["absolute_error_km"] for r in eligible) / len(eligible)
        if eligible
        else None,
        "bias_km": sum(r["difference_km"] for r in eligible) / len(eligible)
        if eligible
        else None,
        "predicted_km": predicted,
        "actual_km": actual,
        "aggregate_error_pct": 100 * (actual - predicted) / actual if actual else None,
        "missing_predictions": sum(r["predicted_km"] is None for r in rows),
        "insufficient_actual": sum(
            r["actual_quality"] != "observed" or r["actual_km"] is None for r in rows
        ),
    }
