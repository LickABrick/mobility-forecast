from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.calendar_manager import (
    CalendarResponseError,
    fetch_events,
)
from custom_components.mobility_forecast.coordinator import VehicleCoordinator


@pytest.mark.parametrize(
    "error,category,status",
    [
        (RuntimeError("PRIVATE ADDRESS"), "calendar_fetch", "calendar_unavailable"),
        (
            CalendarResponseError("PRIVATE TITLE"),
            "calendar_normalization",
            "calendar_unavailable",
        ),
        (TimeoutError("PRIVATE"), "refresh_timeout", "routing_timeout"),
    ],
)
async def test_safe_failure_categories(hass, caplog, error, category, status):
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={"calendars": ["calendar.car"], "routing": True},
    )
    entry.add_to_hass(hass)
    runtime = VehicleCoordinator(hass, entry)
    with patch(
        "custom_components.mobility_forecast.calendar_manager.fetch_events",
        side_effect=error,
    ):
        runtime._schedule_calendar(datetime.now(UTC))
        await runtime.calendar_task
        assert runtime.calendar_status == status
        assert runtime.calendar_metrics["last_failure"] == category
        assert "PRIVATE" not in caplog.text
    await runtime.shutdown()


async def test_response_shape_validation(hass):
    now = datetime.now(UTC)
    with patch.object(
        type(hass.services),
        "async_call",
        return_value={"calendar.car": {"events": "bad"}},
    ):
        with pytest.raises(CalendarResponseError):
            await fetch_events(hass, ["calendar.car"], now, now)
