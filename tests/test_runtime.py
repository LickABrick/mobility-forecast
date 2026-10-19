from unittest.mock import patch

from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_setup_unload_and_removal(hass):
    hass.states.async_set(
        "sensor.odometer",
        "12000",
        {
            "unit_of_measurement": "km",
            "device_class": "distance",
            "state_class": "total_increasing",
        },
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Car",
        data={"odometer": "sensor.odometer"},
        unique_id="sensor.odometer",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert (
            len(
                [
                    s
                    for s in hass.states.async_all("sensor")
                    if s.entity_id != "sensor.odometer"
                ]
            )
            == 5
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
