"""Action-style manual sync switch, intentionally never restored as on."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ManualSyncSwitch(entry.runtime_data)])


class ManualSyncSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "manual_sync"
    _attr_icon = "mdi:sync"

    def __init__(self, coordinator):
        self.controller = coordinator.manual_sync
        self._attr_unique_id = f"{coordinator.entry.entry_id}_manual_sync"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)}
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.controller.listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self.controller.listeners.remove(self.async_write_ha_state)
        )

    @property
    def is_on(self):
        return self.controller.running

    @property
    def extra_state_attributes(self):
        controller = self.controller
        return {
            "status": controller.status,
            "last_triggered_at": controller.requested_at.isoformat()
            if controller.requested_at
            else None,
            "last_started_at": controller.started_at.isoformat()
            if controller.started_at
            else None,
            "last_finished_at": controller.finished_at.isoformat()
            if controller.finished_at
            else None,
            "last_error_code": controller.error,
        }

    async def async_turn_on(self, **kwargs):
        self.controller.trigger()

    async def async_turn_off(self, **kwargs):
        # Runtime state owns off; a user-off is not a cancellation request.
        return
