"""Config-entry lifecycle for the Mobility Forecast integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .runtime import ProfileRuntimeData, build_pending_runtime

PLATFORMS: Final = ("sensor",)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> bool:
    """Set up one isolated profile runtime and its read-only platforms."""

    entry.runtime_data = build_pending_runtime(entry.entry_id)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        entry.runtime_data = None
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> bool:
    """Unload profile platforms and release runtime data only on success."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data = None
    return unload_ok
