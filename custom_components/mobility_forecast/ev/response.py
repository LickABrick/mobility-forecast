"""Read-only local-calendar-day view of a seven-day calculation.

Filtering is not optimization. Shortened responses deliberately do not claim a
reserve assessment or reuse targets calculated for a different energy horizon.
"""

from copy import deepcopy
from datetime import datetime, time, timedelta


def horizon_response(source, days, now, forecasts, consumption):
    result = deepcopy(source)
    cutoff = datetime.combine(now.date() + timedelta(days=days), time(), now.tzinfo)
    result["calculation_horizon_days"] = 7
    result["response_horizon_days"] = days
    result["assessment_scope"] = "full" if days == 7 else "filtered_not_recalculated"
    result["opportunities"] = [
        item
        for item in result.get("opportunities", [])
        if now <= datetime.fromisoformat(item["start"]) < cutoff
        and datetime.fromisoformat(item["end"]) <= cutoff
    ]
    result["unallocated_demand"] = [
        item
        for item in result.get("unallocated_demand", [])
        if now.date().isoformat() <= item["date"] < cutoff.date().isoformat()
    ]
    if days < 7:
        result.update(
            status="insufficient_data",
            reason="shortened_horizon_not_recalculated",
            recommendation=None,
            alternative=None,
            shortfall_at=None,
        )
    selected = [day for day in forecasts if now.date() <= day.day < cutoff.date()]
    result["energy_demand_kwh"] = (
        None
        if any(day.total_km is None or day.baseline_km is None for day in selected)
        else sum(
            day.total_km * consumption / 100
            for day in forecasts
            if now.date() <= day.day < cutoff.date()
        )
    )
    return result
