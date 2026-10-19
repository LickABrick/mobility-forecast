import json
from pathlib import Path

import pytest
from homeassistant.core import State

from custom_components.mobility_forecast.config_flow import vehicle_schema
from custom_components.mobility_forecast.odometer import InvalidReading, validate_source


@pytest.mark.parametrize(
    "entity,unit,attrs",
    [
        ("sensor.odometer", "km", {"device_class": "distance"}),
        ("sensor.mileage", "mi", {}),
        ("sensor.car_counter", "km", {"state_class": "total_increasing"}),
    ],
)
def test_compatible_nonstandard_sources(entity, unit, attrs):
    assert (
        validate_source(State(entity, "100", {"unit_of_measurement": unit, **attrs}))
        > 0
    )


@pytest.mark.parametrize(
    "entity",
    ["sensor.trip_mileage", "sensor.battery_range", "sensor.remaining_mileage"],
)
def test_misleading_names_rejected(entity):
    with pytest.raises(InvalidReading):
        validate_source(
            State(
                entity,
                "100",
                {"unit_of_measurement": "km", "state_class": "total_increasing"},
            )
        )


def test_native_filter_has_unit_fallback():
    selector = next(
        value
        for key, value in vehicle_schema().schema.items()
        if key.schema == "odometer"
    )
    filters = selector.config["filter"]
    assert {"domain": ["sensor"], "unit_of_measurement": ["km", "mi"]} in filters
    for language in ("en", "nl"):
        text = json.loads(
            Path(
                f"custom_components/mobility_forecast/translations/{language}.json"
            ).read_text()
        )
        assert set(text["config"]["step"]["user"]["data"]) == {"name", "odometer"}
