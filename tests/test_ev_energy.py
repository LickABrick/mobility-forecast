import pytest

from custom_components.mobility_forecast.ev.energy import (
    charge_estimate,
    drive_energy,
    reserve_range,
)
from custom_components.mobility_forecast.ev.models import EVConfig


@pytest.mark.parametrize("power", [7.4, 11, 22])
def test_energy_efficiency_and_vehicle_limit(power):
    battery, grid, minutes = charge_estimate(60, 40, 80, power, 22)
    assert battery == 24
    assert grid == pytest.approx(24 / 0.9)
    assert minutes == pytest.approx(60 * 24 / 0.9 / power)
    assert charge_estimate(60, 80, 80, power, 22) == (0, 0, 0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 101, "unknown"])
def test_invalid_soc(value):
    with pytest.raises((ValueError, TypeError)):
        charge_estimate(60, value, 80, 11, 22)


def test_range_and_driving():
    assert reserve_range(EVConfig(60, 20, 11), 40) == 75
    assert drive_energy(100, 20) == 20
