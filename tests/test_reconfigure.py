from unittest.mock import patch

from homeassistant.config_entries import SOURCE_RECONFIGURE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_reconfigure_preserves_entry_identity(hass):
    for name in ("old", "new"):
        hass.states.async_set(
            f"sensor.{name}_odometer",
            "100",
            {"unit_of_measurement": "km", "state_class": "total_increasing"},
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Car",
        data={"odometer": "sensor.old_odometer"},
        unique_id="stable",
    )
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"odometer": "sensor.missing"}
    )
    assert flow["errors"]["odometer"] == "invalid_source"
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"odometer": "sensor.new_odometer"}
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "stable"
    assert entry.data["odometer"] == "sensor.new_odometer"
