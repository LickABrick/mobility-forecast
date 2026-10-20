"""Strict unit-aware telemetry interpretation. Unknown is never zero."""

OPTIONAL_UNITS = {
    "range_entity": ("km", "mi"),
    "charging_power_entity": ("W", "kW"),
    "vehicle_charge_limit_entity": ("%",),
    "remaining_charge_time_entity": ("min", "h", "s"),
    "consumption_entity": ("kWh/100km", "kWh/100 km", "Wh/km"),
    "energy_added_entity": ("kWh", "Wh"),
}
