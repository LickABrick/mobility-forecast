from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from custom_components.mobility_forecast.calendar_manager import (
    CalendarResponseError,
    fetch_events,
)


async def test_bad_items_do_not_break_two_calendars(hass):
    row = {
        "start": "2026-03-29T09:00:00+02:00",
        "end": "2026-03-29T10:00:00+02:00",
        "location": "52,5",
    }
    bad = [
        None,
        [],
        {},
        {**row, "start": "nonsense"},
        {**row, "end": row["start"]},
        {**row, "end": 42},
    ]
    response = {
        "calendar.a": {"events": [row] * 149 + bad},
        "calendar.b": {"events": [{**row, "status": "cancelled"}]},
    }
    start = datetime(2026, 3, 29, tzinfo=UTC)
    with patch("homeassistant.core.ServiceRegistry.async_call", return_value=response):
        events = await fetch_events(
            hass, ["calendar.a", "calendar.b"], start, start + timedelta(days=1)
        )
    assert len(events) == 1
    assert events.retrieved_count == 156
    assert events.invalid_count == 6


@pytest.mark.parametrize("response", [None, [], {}, {"calendar.a": {"events": {}}}])
async def test_response_errors_remain_strict(hass, response):
    now = datetime.now(UTC)
    with patch("homeassistant.core.ServiceRegistry.async_call", return_value=response):
        with pytest.raises(CalendarResponseError):
            await fetch_events(hass, ["calendar.a"], now, now)
