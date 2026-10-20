from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN


async def test_disabled_identity_preserved_on_reload(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Car", data={"odometer": "sensor.car"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    disabled = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_today",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        before = {
            e.unique_id: e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        assert len(before) == 7  # Six sensors plus the action-style sync switch.
        timeline = registry.async_get(before[f"{entry.entry_id}_mileage_timeline"])
        assert timeline.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(timeline.entity_id) is None
        assert hass.states.get(disabled.entity_id) is None
        assert await hass.config_entries.async_reload(entry.entry_id)
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        assert before == {
            e.unique_id: e.entity_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        assert (
            len(
                [
                    e
                    for e in er.async_entries_for_config_entry(registry, entry.entry_id)
                    if e.entity_id.startswith("sensor.")
                    and hass.states.get(e.entity_id)
                ]
            )
            == 4
        )
        await hass.config_entries.async_unload(entry.entry_id)
