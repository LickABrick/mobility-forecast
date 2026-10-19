import pytest
from homeassistant.core import State

from custom_components.mobility_forecast.odometer import InvalidReading, validate_source


def test_odometer_source():
    assert (
        validate_source(State("sensor.odometer", "100", {"unit_of_measurement": "km"}))
        == 100
    )


@pytest.mark.parametrize(
    "entity,attrs",
    [
        ("sensor.range", {"state_class": "total"}),
        ("sensor.distance", {}),
        ("sensor.trip", {}),
    ],
)
def test_unsuitable_source(entity, attrs):
    with pytest.raises(InvalidReading):
        validate_source(State(entity, "10", {"unit_of_measurement": "km", **attrs}))
