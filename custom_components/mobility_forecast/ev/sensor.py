"""Six optional EV entities, no control services or recorder timelines."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN

DESCRIPTIONS = {
    "ev_estimated_range": (
        SensorDeviceClass.DISTANCE,
        UnitOfLength.KILOMETERS,
        "estimated_range_km",
    ),
    "ev_next_charge_start": (SensorDeviceClass.TIMESTAMP, None, "start"),
    "ev_target_soc": (None, "%", "target_soc"),
    "ev_charge_energy_needed": (
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        "battery_energy_kwh",
    ),
    "ev_estimated_charge_duration": (
        SensorDeviceClass.DURATION,
        UnitOfTime.MINUTES,
        "duration_minutes",
    ),
    "ev_charge_forecast_status": (None, None, "status"),
}


class EVSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = None

    def __init__(self, parent, key):
        self.parent = parent
        self.key = key
        self._attr_unique_id = f"{parent.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_class, self._attr_native_unit_of_measurement, self.field = (
            DESCRIPTIONS[key]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, parent.entry.entry_id)}
        )
        self.last_value = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        runtime = self.parent.ev
        if runtime:
            runtime.listeners.append(self.update_state)
            self.async_on_remove(lambda: runtime.listeners.remove(self.update_state))
        else:
            self.async_on_remove(self.parent.async_add_listener(self.attach))

    def attach(self):
        if self.parent.ev and self.update_state not in self.parent.ev.listeners:
            self.parent.ev.listeners.append(self.update_state)
            self.async_on_remove(
                lambda: self.parent.ev.listeners.remove(self.update_state)
            )

    def update_state(self):
        value = (self.native_value, self.extra_state_attributes)
        if value != self.last_value:
            self.last_value = value
            self.async_write_ha_state()

    @property
    def native_value(self):
        data = self.parent.ev.result if self.parent.ev else {}
        if self.field == "status":
            return data.get("status", "insufficient_data")
        if self.field == "estimated_range_km":
            return (
                data.get(self.field)
                if data.get("telemetry", {}).get("freshness") == "fresh"
                else None
            )
        recommendation = data.get("recommendation") or {}
        value = recommendation.get(self.field)
        if self.field == "start" and value:
            from datetime import datetime

            return datetime.fromisoformat(value)
        return value

    @property
    def extra_state_attributes(self):
        if self.field != "status":
            return {}
        data = self.parent.ev.result if self.parent.ev else {}
        rec = data.get("recommendation") or {}
        return {
            "reason": data.get("reason", "initializing"),
            "confidence": rec.get("confidence", "insufficient_data"),
            "location_type": rec.get("location_type"),
            "telemetry_freshness": data.get("telemetry", {}).get(
                "freshness", "unavailable"
            ),
            "charger_distance_m": rec.get("charger_distance_m"),
        }
