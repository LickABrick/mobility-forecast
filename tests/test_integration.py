from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER

from custom_components.mobility_forecast.const import DOMAIN


async def test_native_flow(hass):
    hass.states.async_set(
        "sensor.odometer",
        "12000",
        {
            "unit_of_measurement": "km",
            "device_class": "distance",
            "state_class": "total_increasing",
        },
    )
    with patch(
        "custom_components.mobility_forecast.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == "form"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"odometer": "sensor.odometer"}
        )
        assert result["type"] == "create_entry"
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {"odometer": "sensor.odometer"}
        )
        assert second["reason"] == "already_configured"
