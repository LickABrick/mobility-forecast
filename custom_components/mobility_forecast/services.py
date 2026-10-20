"""Bounded read-only native response actions; never expose itinerary content."""

from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .comparison import comparisons, metrics
from .const import DOMAIN


def history_data(runtime, days=30):
    now = dt_util.utcnow().astimezone(ZoneInfo(runtime.hass.config.time_zone))
    records = comparisons(
        runtime.store.payload["snapshots"], runtime.history_cache, now, 365
    )
    return {
        "entry_id": runtime.entry.entry_id,
        "timezone": runtime.hass.config.time_zone,
        "history": records[-days:],
        "accuracy": {str(period): metrics(records, period) for period in (7, 30, 90)},
    }


def forecast_data(runtime):
    from datetime import datetime, time

    data = runtime.data
    zone = ZoneInfo(runtime.hass.config.time_zone)
    return {
        "entry_id": runtime.entry.entry_id,
        "calculated_at": data.generated_at.isoformat(),
        "forecast": [
            {
                "date": d.day.isoformat(),
                "timestamp": datetime.combine(d.day, time(), zone).isoformat(),
                "predicted_km": d.total_km,
                "low_km": d.low_km,
                "high_km": d.high_km,
            }
            for d in data.days[:31]
        ],
    }


def register_services(hass):
    if hass.services.has_service(DOMAIN, "get_history"):
        return

    async def handle(call):
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or not hasattr(entry, "runtime_data")
            or not entry.runtime_data.initialized
        ):
            raise HomeAssistantError("Vehicle is not loaded")
        runtime = entry.runtime_data
        return (
            history_data(runtime, call.data["days"])
            if call.service == "get_history"
            else forecast_data(runtime)
        )

    schema = vol.Schema(
        {
            vol.Required("entry_id"): str,
            vol.Optional("days", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=365)
            ),
        }
    )
    for name in ("get_history", "get_forecast"):
        hass.services.async_register(
            DOMAIN, name, handle, schema=schema, supports_response=SupportsResponse.ONLY
        )
