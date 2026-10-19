from datetime import UTC, datetime
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.coordinator import VehicleCoordinator
from custom_components.mobility_forecast.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.mobility_forecast.sensor import ForecastSensor


async def test_progress_is_privacy_safe(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.private"], "routing": True, "region": "eu"},
    )
    entry.add_to_hass(hass)
    runtime = entry.runtime_data = VehicleCoordinator(hass, entry)
    runtime.calendar_metrics = {
        "events_count": 150,
        "nested_ignored": 100,
        "days_complete": 2,
        "days_pending": 28,
        "last_failure": "refresh_timeout",
    }
    sensor = ForecastSensor(runtime, "today")
    assert sensor.extra_state_attributes["calendar_nested_ignored"] == 100
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["calendar_progress"]["events_count"] == 150
    assert "calendar.private" not in str(diagnostics)
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        return_value=[],
    ):
        runtime._schedule_calendar(datetime.now(UTC))
        await runtime.calendar_task
        assert runtime.calendar_status == "ready"
        assert runtime.calendar_metrics["days_pending"] == 0
    await runtime.shutdown()
