"""Five native distance predictions per logical vehicle."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FORECAST_KEYS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(ForecastSensor(entry.runtime_data, key) for key in FORECAST_KEYS)


class ForecastSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Mobility Forecast",
            model="Distance forecast",
        )

    @property
    def available(self):
        # Unknown forecasts and source/model errors are meaningful states, not
        # grounds for hiding the entity behind coordinator availability.
        return True

    @property
    def native_value(self):
        return (
            self.coordinator.data.values.get(self.key)
            if self.coordinator.data
            else None
        )

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if data is None:
            return {"forecast_status": "initializing"}
        return {
            "forecast_status": data.status.value,
            "history_import_status": getattr(
                self.coordinator, "import_status", "pending"
            ),
            "generated_at": data.generated_at.isoformat(),
            "data_quality": data.quality,
            "history_days": data.history_days,
            "calendar_included": any(d.planned_km is not None for d in data.days[:31]),
            "calendar_status": self.coordinator.calendar_status,
            **{
                f"calendar_{key}": value
                for key, value in self.coordinator.calendar_metrics.items()
            },
        }
