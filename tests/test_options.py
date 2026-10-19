from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_locations_native_crud(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"odometer": "sensor.odometer"},
        options={"known_locations": {"Old": "52,5"}},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mobility_forecast.async_setup_entry", return_value=True
    ):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        assert flow["type"] == "menu"
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "locations"}
        )
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "add_location"}
        )
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"name": "Office", "address": "Office"}
        )
        assert flow["errors"] == {"base": "invalid_location"}
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"name": "Office", "address": "53,6"}
        )
        assert flow["type"] == "create_entry"
        assert entry.options["known_locations"] == {"Old": "52,5", "Office": "53,6"}
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        for step in ["locations", "remove_location"]:
            flow = await hass.config_entries.options.async_configure(
                flow["flow_id"], {"next_step_id": step}
            )
        await hass.config_entries.options.async_configure(
            flow["flow_id"], {"location": "Old"}
        )
        assert "Old" not in entry.options["known_locations"]


async def test_calendar_enable_dependency_and_disable(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"odometer": "sensor.odometer"},
        options={"known_locations": {"Office": "52,5"}},
    )
    entry.add_to_hass(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "calendars"}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"calendars": [], "routing": True}
    )
    assert flow["errors"]["base"] == "routing_unavailable"
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"calendars": [], "routing": False}
    )
    assert result["type"] == "create_entry"
    assert entry.options["known_locations"] == {"Office": "52,5"}
