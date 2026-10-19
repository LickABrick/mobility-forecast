"""Diagnostics omit configuration, event content, locations and raw history."""

from .const import VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = entry.runtime_data
    data = runtime.data
    return {
        "version": VERSION,
        "status": data.status.value if data else "initializing",
        "history_days": data.history_days if data else 0,
        "data_quality": data.quality if data else "insufficient",
        "valid_samples": len(runtime.readings),
        "rejected_samples": runtime.rejected,
        "storage_readable": not runtime.store.corrupt,
        "calendar_count": len(entry.options.get("calendars", [])),
        "calendar_status": runtime.calendar_status,
        "calendar_progress": dict(runtime.calendar_metrics),
        "route_cache_statistics_scope": "last_processing_cycle",
        "route_cache_statistics": dict(runtime.route_metrics),
        "cached_routes": len(runtime.store.payload["routes"]),
        "evaluation": runtime.store.payload["evaluation"],
    }
