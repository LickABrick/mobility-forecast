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
        if call.service == "get_ev_plan":
            if not runtime.ev:
                return {"schema": 1, "entry_id": entry.entry_id, "status": "disabled"}
            from copy import deepcopy
            from datetime import datetime, time, timedelta

            result = deepcopy(runtime.ev.result)
            now = dt_util.utcnow().astimezone(ZoneInfo(hass.config.time_zone))
            cutoff = datetime.combine(
                now.date() + timedelta(days=call.data["horizon_days"]),
                time(),
                now.tzinfo,
            )
            result["calculation_horizon_days"] = 7
            result["response_horizon_days"] = call.data["horizon_days"]
            result["opportunities"] = [
                item
                for item in result.get("opportunities", [])
                if datetime.fromisoformat(item["start"]) < cutoff
                and datetime.fromisoformat(item["end"]) <= cutoff
            ]
            for key in ("recommendation", "alternative"):
                item = result.get(key)
                if (
                    item
                    and item.get("start")
                    and datetime.fromisoformat(item["start"]) >= cutoff
                ):
                    result[key] = None
            result["energy_demand_kwh"] = sum(
                day.total_km * runtime.ev.config.consumption_kwh_per_100km / 100
                for day in runtime.data.days
                if now.date() <= day.day < cutoff.date()
            )
            return {"entry_id": entry.entry_id, **result}
        return (
            history_data(runtime, call.data["days"])
            if call.service == "get_history"
            else forecast_data(runtime)
        )

    async def sync_now(call):
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or not hasattr(entry, "runtime_data")
            or entry.runtime_data.stopping
        ):
            raise HomeAssistantError("Vehicle is not loaded")
        await entry.runtime_data.manual_sync.request()

    hass.services.async_register(
        DOMAIN, "sync_now", sync_now, schema=vol.Schema({vol.Required("entry_id"): str})
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

    hass.services.async_register(
        DOMAIN,
        "get_ev_plan",
        handle,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Optional("horizon_days", default=7): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=7)
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
