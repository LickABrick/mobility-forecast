"""Config-entry lifecycle for the Mobility Forecast integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .ha_calendar import CONF_CALENDAR_ENTITY_IDS
from .runtime import ProfileRuntimeData, build_runtime

PLATFORMS: Final = ("sensor",)
CONFIG_ENTRY_VERSION: Final = 1
CONFIG_ENTRY_MINOR_VERSION: Final = 2


async def async_migrate_entry(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> bool:
    """Migrate the pre-calendar config contract without guessing a source.

    Version 1.1 entries contained no behavioral data. The empty list is an
    explicit legacy-unconfigured marker, not a calendar default; strict source
    decoding rejects it until a calendar is selected by a later user flow.
    """

    if entry.version != CONFIG_ENTRY_VERSION:
        return False
    if entry.minor_version == CONFIG_ENTRY_MINOR_VERSION:
        return True
    if entry.minor_version != 1 or entry.data:
        return False
    hass.config_entries.async_update_entry(
        entry,
        data={CONF_CALENDAR_ENTITY_IDS: []},
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> bool:
    """Set up one isolated profile runtime and its read-only platforms."""

    runtime = build_runtime(hass, entry)
    entry.runtime_data = runtime
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        runtime.start(hass)
        await runtime.async_refresh()
    except Exception:
        runtime.stop()
        entry.runtime_data = None
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> bool:
    """Unload profile platforms and release runtime data only on success."""

    runtime = entry.runtime_data
    if runtime is None:
        return False
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime.stop()
        entry.runtime_data = None
    return unload_ok
