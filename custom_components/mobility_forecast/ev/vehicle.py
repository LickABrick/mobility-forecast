"""Strict unit-aware telemetry interpretation. Unknown is never zero."""

OPTIONAL_UNITS = {
    "range_entity": ("km", "mi"),
    "charging_power_entity": ("W", "kW"),
    "vehicle_charge_limit_entity": ("%",),
    "remaining_charge_time_entity": ("min", "h", "s"),
    "consumption_entity": ("kWh/100km", "kWh/100 km", "Wh/km"),
    "energy_added_entity": ("kWh", "Wh"),
}


def telemetry(hass, options, now, readings=()):
    from .energy import number
    from .models import VehicleTelemetry

    def numeric(key, units, maximum=1e6):
        state = hass.states.get(options.get(key, ""))
        if state is None or state.attributes.get("unit_of_measurement") not in units:
            return None
        try:
            return (
                number(state.state, 0, maximum)
                * units[state.attributes["unit_of_measurement"]]
            )
        except ValueError, TypeError:
            return None

    state = hass.states.get(options.get("soc_entity", ""))
    soc = numeric("soc_entity", {"%": 1}, 100)
    stamp = state.last_reported if state and soc is not None else None
    freshness = (
        "unavailable"
        if stamp is None
        else "fresh"
        if 0 <= (now - stamp).total_seconds() <= 21600
        else "stale"
    )
    if stamp and any(
        r.timestamp > stamp
        and r.km
        > max((old.km for old in readings if old.timestamp <= stamp), default=r.km)
        for r in readings
    ):
        freshness = "driving_since_soc"

    def text(key):
        value = hass.states.get(options.get(key, ""))
        return value.state.casefold() if value else "unknown"

    charging = {
        "on": "charging",
        "charging": "charging",
        "laden": "charging",
        "paused": "paused",
        "gepauzeerd": "paused",
        "faulted": "faulted",
        "completed": "completed",
        "stopped": "idle",
        "off": "idle",
        "connected": "idle",
    }.get(text("charging_state_entity"), "unknown")
    plugged = {"on": True, "connected": True, "off": False, "disconnected": False}.get(
        text("plugged_in_entity")
    )
    location = text("vehicle_location_entity")
    return VehicleTelemetry(
        soc,
        stamp,
        freshness,
        charging,
        plugged,
        numeric("charging_power_entity", {"W": 0.001, "kW": 1}),
        numeric("vehicle_charge_limit_entity", {"%": 1}, 100),
        numeric("range_entity", {"km": 1, "mi": 1.609344}),
        numeric("remaining_charge_time_entity", {"min": 1, "h": 60, "s": 1 / 60}),
        location if location in ("home", "not_home") else None,
        numeric(
            "consumption_entity", {"kWh/100km": 1, "kWh/100 km": 1, "Wh/km": 0.1}, 1000
        ),
    )
