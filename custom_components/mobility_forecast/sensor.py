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
    from homeassistant.helpers import entity_registry as er

    from .status_sensor import KEYS, DiagnosticSensor

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_mileage_timeline"
    )
    if (
        entity_id
        and registry.async_get(entity_id).disabled_by
        == er.RegistryEntryDisabler.INTEGRATION
    ):
        registry.async_update_entity(entity_id, disabled_by=None)
    async_add_entities(DiagnosticSensor(entry.runtime_data, key) for key in KEYS)
    if entry.options.get("ev_enabled"):
        from .ev.sensor import DESCRIPTIONS, EVSensor

        async_add_entities(EVSensor(entry.runtime_data, key) for key in DESCRIPTIONS)
    async_add_entities(
        [
            *(ForecastSensor(entry.runtime_data, key) for key in FORECAST_KEYS),
            TimelineSensor(entry.runtime_data),
        ]
    )


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
            # Rolling calculations must not churn all five entity attributes.
            # Calculation timestamps are available through the read-only API.
            "data_quality": data.quality,
            "history_days": data.history_days,
            "calendar_included": any(d.planned_km is not None for d in data.days[:31]),
            "calendar_status": self.coordinator.calendar_status,
            **{
                key: value
                for key, value in self.coordinator.route_metrics.items()
                if key
                in (
                    "route_cache_entries",
                    "route_cache_hits",
                    "waze_requests",
                    "waze_failures",
                )
            },
            **{
                f"calendar_{key}": value
                for key, value in self.coordinator.calendar_metrics.items()
            },
        }


class TimelineSensor(ForecastSensor):
    """Default-enabled bounded series, never duplicated onto forecasts."""

    _attr_entity_registry_enabled_default = True
    _attr_device_class = None
    _attr_state_class = None
    _attr_suggested_display_precision = None
    _attr_native_unit_of_measurement = None
    _unrecorded_attributes = frozenset({"history", "forecast", "accuracy"})

    def __init__(self, coordinator):
        super().__init__(coordinator, "mileage_timeline")

    @property
    def native_value(self):
        return self.coordinator.data.status.value

    @property
    def extra_state_attributes(self):
        from .services import forecast_data, history_data

        history = history_data(self.coordinator)
        future = forecast_data(self.coordinator)
        return {
            "history": history["history"],
            "forecast": future["forecast"],
            "accuracy": history["accuracy"],
            "timezone": history["timezone"],
        }
