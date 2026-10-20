"""Pure AC battery/grid calculations. Efficiency applies exactly once."""

import math

EFFICIENCY = 0.90


def number(value, minimum=0, maximum=1e9):
    if isinstance(value, bool):
        raise ValueError("invalid_numeric_input")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError("invalid_numeric_input")
    return result


def drive_energy(distance_km, consumption_kwh_per_100km):
    return number(distance_km) * number(consumption_kwh_per_100km, 0.001, 100) / 100


def battery_energy(capacity_kwh, soc_percent):
    return number(capacity_kwh, 0.001, 300) * number(soc_percent, 0, 100) / 100


def reserve_range(config, soc_percent, consumption=None):
    return (
        max(
            0,
            battery_energy(config.usable_capacity_kwh, soc_percent)
            - battery_energy(config.usable_capacity_kwh, config.minimum_soc),
        )
        * 100
        / number(consumption or config.consumption_kwh_per_100km, 0.001, 100)
    )


def charge_estimate(capacity_kwh, current_soc, target_soc, vehicle_kw, charger_kw):
    energy = battery_energy(
        capacity_kwh, max(0, number(target_soc, 0, 100) - number(current_soc, 0, 100))
    )
    power = min(number(vehicle_kw, 0.001, 43), number(charger_kw, 0.001, 43))
    grid = energy / EFFICIENCY
    return energy, grid, 60 * grid / power
