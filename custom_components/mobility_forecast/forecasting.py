"""Deterministic robust forecasting, independent of Home Assistant."""

from datetime import UTC, datetime, time, timedelta
from math import sqrt
from statistics import pstdev

from .const import FORECAST_KEYS
from .models import DailyDistance, DailyForecast, Forecast, Status

MIN_USEFUL_DAYS = 7
WEEKDAY_DAYS = 28
TREND_DAYS = 56
WEEKDAY_PRIOR = 4


def robust_mean(values: list[float]) -> float:
    """Winsorize isolated extremes using median absolute deviation."""
    positive = sorted(v for v in values if v > 0)
    if not positive:
        return 0.0
    # Hurdle estimator: parked days affect use probability, not the distance
    # distribution conditional on driving. Only an isolated, very large upper
    # tail is capped; recurring long trips remain part of expected consumption.
    # With <5 driving samples there is no defensible outlier evidence.
    adjusted = positive[:]
    if len(positive) >= 5:
        reference = positive[max(0, int((len(positive) - 1) * 0.8))]
        ceiling = max(reference * 3, reference + 50)
        exceptional = [v for v in positive if v > ceiling]
        if len(exceptional) <= max(1, int(len(positive) * 0.05)):
            adjusted = [min(v, ceiling) for v in positive]
    return (len(positive) / len(values)) * (sum(adjusted) / len(positive))


def predict(
    history: list[DailyDistance], now: datetime, plans: dict | None = None
) -> Forecast:
    if now.tzinfo is None:
        raise ValueError("Forecast clock must be timezone aware")
    history = sorted(history, key=lambda d: d.day)
    useful = [
        d
        for d in history
        if d.day < now.date()
        and d.km is not None
        and d.coverage >= 0.9
        and (now.date() - d.day).days <= 365
    ]
    result = Forecast(
        now, Status.LEARNING, dict.fromkeys(FORECAST_KEYS), history_days=len(useful)
    )
    if len(useful) < MIN_USEFUL_DAYS:
        return result
    precise = [d for d in useful if d.quality == "observed"]
    baseline = robust_mean([float(d.km) for d in useful if d.km is not None])
    trend = 1.0
    if len(useful) >= TREND_DAYS and baseline > 0:
        recent = robust_mean([float(d.km) for d in useful[-28:] if d.km is not None])
        trend = min(1.5, max(0.5, recent / baseline))
    weekday = {}
    for index in range(7):
        # A mature recent regime should replace obsolete parked/commuter
        # frequency, not merely scale a year-old weekday mixture.
        weekday_history = precise[-56:] if len(precise) >= 112 else precise
        samples = [
            float(d.km)
            for d in weekday_history
            if d.day.weekday() == index and d.km is not None
        ]
        if len(precise) >= WEEKDAY_DAYS and len(samples) >= 3:
            weight = len(samples) / (len(samples) + WEEKDAY_PRIOR)
            weekday[index] = (
                weight * robust_mean(samples) + (1 - weight) * baseline
            ) * trend
        else:
            weekday[index] = baseline * trend
    deviation = pstdev([float(d.km) for d in useful if d.km is not None])
    coverage_penalty = 1 + (1 - len(precise) / len(useful))
    width = (
        max(deviation, baseline * 0.15) * coverage_penalty * (1 + 1 / sqrt(len(useful)))
    )
    result.status = Status.READY if len(precise) >= WEEKDAY_DAYS else Status.PROVISIONAL
    result.quality = "daily" if len(precise) >= WEEKDAY_DAYS else "estimated"
    plans = plans or {}
    for offset in range(366):
        day = now.date() + timedelta(days=offset)
        normal = max(0, weekday[day.weekday()])
        planned = plans.get(day) if offset <= 30 else None
        route = planned.distance_km if planned is not None else None
        complete = planned.complete if planned is not None else True
        total = max(normal, route or 0)
        if offset == 0:
            actual = next((d.minimum_km for d in history if d.day == day), 0)
            total = max(total, actual)
        uncertainty = width * (1 if complete else 1.5)
        result.days.append(
            DailyForecast(
                day,
                normal,
                total,
                max(0, total - uncertainty),
                total + uncertainty,
                route,
                complete,
            )
        )
    # Rolling N local days: remaining fraction today + N-1 full days + elapsed fraction final day.
    midnight = datetime.combine(now.date(), time(), now.tzinfo)
    next_midnight = datetime.combine(now.date() + timedelta(days=1), time(), now.tzinfo)
    fraction = (now.astimezone(UTC) - midnight.astimezone(UTC)).total_seconds() / (
        next_midnight.astimezone(UTC) - midnight.astimezone(UTC)
    ).total_seconds()

    def rolling(count: int) -> float:
        return (
            max(
                0,
                result.days[0].total_km
                - max(
                    fraction * result.days[0].baseline_km,
                    next((d.minimum_km for d in history if d.day == now.date()), 0),
                ),
            )
            + sum(d.total_km for d in result.days[1:count])
            + fraction * result.days[count].total_km
        )

    result.values = {
        "today": result.days[0].total_km,
        "tomorrow": result.days[1].total_km,
        "next_7_days": rolling(7),
        "next_30_days": rolling(30),
        "annual": sum(d.baseline_km for d in result.days[:365]),
    }
    return result


def evaluate(
    snapshots: dict[str, float], history: list[DailyDistance]
) -> dict[str, float | int]:
    errors = [
        snapshots[d.day.isoformat()] - d.km
        for d in history
        if d.quality == "observed"
        and d.coverage >= 0.99
        and d.km is not None
        and d.day.isoformat() in snapshots
    ]
    return {
        "count": len(errors),
        "mae_km": sum(abs(e) for e in errors) / len(errors) if errors else 0,
        "bias_km": sum(errors) / len(errors) if errors else 0,
    }
