"""Config-entry lifecycle for the Mobility Forecast integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .ha_calendar import CONF_CALENDAR_ENTITY_IDS, validate_calendar_entity_ids
from .profile_config import (
    CONF_ALL_DAY_EVENT_POLICY,
    CONF_END_ANCHOR_ENTITY_ID,
    CONF_NO_LOCATION_EVENT_POLICY,
    CONF_ONLINE_EVENT_POLICY,
    CONF_PHYSICAL_EVENT_POLICY,
    CONF_START_ANCHOR_ENTITY_ID,
    ProfilePlanningConfig,
)
from .runtime import ProfileRuntimeData, build_runtime

PLATFORMS: Final = ("sensor",)
CONFIG_ENTRY_VERSION: Final = 1
CONFIG_ENTRY_MINOR_VERSION: Final = 4

_PLANNING_DATA_KEYS: Final = {
    CONF_START_ANCHOR_ENTITY_ID,
    CONF_END_ANCHOR_ENTITY_ID,
    CONF_PHYSICAL_EVENT_POLICY,
    CONF_ONLINE_EVENT_POLICY,
    CONF_ALL_DAY_EVENT_POLICY,
    CONF_NO_LOCATION_EVENT_POLICY,
}


async def async_migrate_entry(
    hass: HomeAssistant, entry: ConfigEntry[ProfileRuntimeData]
) -> bool:
    """Migrate earlier config contracts without guessing sources or policy.

    Version 1.1 entries contained no behavioral data. The empty list is an
    explicit legacy-unconfigured marker, not a calendar default; strict source
    decoding rejects it until a calendar is selected by a later user flow.
    Version 1.2 entries keep their calendar selection but gain no guessed
    anchors or event handling; version 1.3 entries keep their explicit planning
    choices but gain no guessed route provider, credential or route preference.
    Users complete absent fields through reconfigure.
    """

    if entry.version != CONFIG_ENTRY_VERSION:
        return False
    if entry.minor_version == CONFIG_ENTRY_MINOR_VERSION:
        return True
    if entry.minor_version == 1:
        if entry.data:
            return False
        data: dict[str, object] = {CONF_CALENDAR_ENTITY_IDS: []}
    elif entry.minor_version == 2:
        if set(entry.data) != {CONF_CALENDAR_ENTITY_IDS}:
            return False
        raw_entity_ids = entry.data[CONF_CALENDAR_ENTITY_IDS]
        if raw_entity_ids != []:
            try:
                validate_calendar_entity_ids(raw_entity_ids)
            except ValueError:
                return False
        data = dict(entry.data)
    elif entry.minor_version == 3:
        if set(entry.data) != {CONF_CALENDAR_ENTITY_IDS, *_PLANNING_DATA_KEYS}:
            return False
        try:
            validate_calendar_entity_ids(entry.data[CONF_CALENDAR_ENTITY_IDS])
            ProfilePlanningConfig.from_entry_data(entry.data)
        except ValueError:
            return False
        data = dict(entry.data)
    else:
        return False
    hass.config_entries.async_update_entry(
        entry,
        data=data,
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
