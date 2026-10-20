"""Compact event-driven diagnostic sensors; properties never request external data."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .forecasting import MIN_USEFUL_DAYS
from .models import Status

KEYS = ("forecast_status", "sync_status", "last_successful_sync", "calendar_status")
CALENDAR_STATES = (
    "disabled",
    "refreshing",
    "cached",
    "provisional",
    "partial",
    "incomplete",
    "ready",
    "calendar_unavailable",
    "routing_unavailable",
    "routing_timeout",
    "stale",
)


class DiagnosticSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, key):
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)}
        )
        self._last = None
        if key == "last_successful_sync":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        else:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = (
                [s.value for s in Status]
                if key == "forecast_status"
                else ["idle", "syncing"]
                if key == "sync_status"
                else list(CALENDAR_STATES)
            )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._changed))
        self.coordinator.manual_sync.listeners.append(self._changed)
        self.async_on_remove(
            lambda: self.coordinator.manual_sync.listeners.remove(self._changed)
        )
        self._last = (self.native_value, self.extra_state_attributes)

    def _changed(self):
        current = (self.native_value, self.extra_state_attributes)
        if current != self._last:
            self._last = current
            self.async_write_ha_state()

    @property
    def native_value(self):
        runtime = self.coordinator
        if self.key == "forecast_status":
            return runtime.data.status.value
        if self.key == "sync_status":
            return runtime.manual_sync.activity
        if self.key == "last_successful_sync":
            return runtime.manual_sync.successful_at
        if not runtime.entry.options.get("calendars") or not runtime.entry.options.get(
            "routing"
        ):
            return "disabled"
        return runtime.calendar_status

    @property
    def extra_state_attributes(self):
        runtime = self.coordinator
        sync = runtime.manual_sync
        if self.key == "sync_status":
            return {
                "phase": sync.phase,
                "last_result": sync.last_result,
                "last_requested_at": sync.requested_at,
                "last_started_at": sync.started_at,
                "last_finished_at": sync.finished_at,
                "duration_seconds": sync.duration_seconds,
                "last_error_code": sync.error,
                "pending_followup": sync.again,
            }
        if self.key == "forecast_status":
            data = runtime.data
            reasons = {
                "learning": "insufficient_history",
                "calendar_only": "verified_calendar_routes_without_history",
                "source_unavailable": "odometer_unavailable",
                "source_incompatible": "odometer_resets",
            }
            return {
                "reason": reasons.get(data.status.value, data.status.value),
                "history_import_status": runtime.import_status,
                "usable_history_days": data.history_days,
                "required_history_days": MIN_USEFUL_DAYS,
                "data_quality": data.quality,
                "calendar_contribution_available": any(
                    d.planned_km is not None for d in data.days[:31]
                ),
            }
        if self.key == "calendar_status":
            metrics = runtime.calendar_metrics
            result = {
                key: metrics[key]
                for key in (
                    "events_routable",
                    "events_without_location",
                    "events_virtual_skipped",
                    "events_invalid_skipped",
                    "nested_ignored",
                    "days_complete",
                    "days_incomplete",
                    "days_pending",
                )
                if key in metrics
            }
            result.update(
                {
                    key: runtime.route_metrics[key]
                    for key in ("route_cache_hits", "waze_requests", "waze_failures")
                    if key in runtime.route_metrics
                }
            )
            result.update(
                selected_calendars_count=len(
                    runtime.entry.options.get("calendars", [])
                ),
                last_fetch_attempt_at=runtime.calendar_attempted_at,
                last_successful_fetch_at=runtime.calendar_refreshed_at,
                events_retrieved=metrics.get("events_count"),
                last_failure_code=metrics.get("last_failure"),
                next_retry_at=runtime.calendar_fetch_retry_at
                or runtime.calendar_next_work,
            )
            return result
        return {}
