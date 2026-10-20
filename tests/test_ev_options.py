from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.config_flow import MobilityOptions  # noqa: F401


async def test_ev_opt_in_validation_and_preservation(hass, enable_custom_integrations):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"known_locations": {"Office": "52,5"}},
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.soc", "unavailable", {"unit_of_measurement": "%"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "ev" in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ev"}
    )
    values = {
        "ev_enabled": True,
        "soc_entity": "sensor.soc",
        "usable_capacity_kwh": 60,
        "consumption_kwh_per_100km": 18,
        "max_ac_charge_power_kw": 11,
        "minimum_soc": 15,
        "preferred_max_soc": 80,
        "charging_mode": "appointments_only",
        "external_lookup_consent": False,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], values
    )
    assert result["errors"]["external_lookup_consent"] == "consent_required"
    values["external_lookup_consent"] = True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], values
    )
    assert result["type"] == "create_entry"
    assert result["data"]["known_locations"] == {"Office": "52,5"}
