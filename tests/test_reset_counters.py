from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.core import State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.odometer import InvalidReading, validate_source


@pytest.mark.parametrize(
    "name",
    ["iphone_walking_running_distance", "daily_distance", "weekly_trip_distance"],
)
def test_reject_known_resetting_names(name):
    with pytest.raises(InvalidReading):
        validate_source(
            State(
                f"sensor.{name}",
                "10",
                {"unit_of_measurement": "km", "state_class": "total_increasing"},
            )
        )


async def test_repeated_resets_preserve_history(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast", data={"odometer": "sensor.odometer"}
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    start = datetime.now(UTC) - timedelta(days=3)
    for day, value in [(0, 100), (1, 5), (1.5, 20), (2, 3)]:
        stamp = start + timedelta(days=day)
        runtime._ingest(
            State(
                "sensor.odometer",
                str(value),
                {"unit_of_measurement": "km"},
                last_reported=stamp,
            )
        )
        if day == 1:
            assert not runtime.source_incompatible
    assert runtime.source_incompatible
    assert runtime.readings[0].km == 100
    assert len(runtime.readings) == 1
    await runtime.shutdown()
