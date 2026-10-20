"""Reconcile timed legs with the complete mobility forecast, without addition."""


def reconcile(days, plans, history, now):
    legs = []
    unallocated = []
    observed = {day.day: day for day in history}
    for forecast in days[:7]:
        plan = plans.get(forecast.day)
        timed = list(plan.legs) if plan and plan.complete else []
        future = [leg for leg in timed if leg.arrival > now]
        legs.extend(future)
        completed = sum(leg.distance_km for leg in timed if leg.arrival <= now)
        actual = observed.get(forecast.day)
        # minimum_km is measured movement, not an interpolation of absent data.
        driven = actual.minimum_km if actual and forecast.day == now.date() else 0
        accounted = max(completed, driven) + sum(leg.distance_km for leg in future)
        extra = max(0, forecast.total_km - accounted)
        if extra:
            unallocated.append({"date": forecast.day.isoformat(), "distance_km": extra})
    return legs, unallocated
