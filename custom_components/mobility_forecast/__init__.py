"""Mobility Forecast entry lifecycle."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import VehicleCoordinator
from .storage import VehicleStore

type MobilityEntry = ConfigEntry[VehicleCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MobilityEntry) -> bool:
    from .services import register_services

    register_services(hass)
    coordinator = entry.runtime_data = VehicleCoordinator(hass, entry)
    # Register the platform before storage, history or model work. A successful
    # config flow must yield entities even if initialization later fails.
    entry.async_on_unload(entry.add_update_listener(async_reload))
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.SWITCH]
    )
    coordinator.start_initialization()
    return True


async def async_reload(hass: HomeAssistant, entry: MobilityEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MobilityEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR, Platform.SWITCH]
    ):
        await entry.runtime_data.shutdown()
        return True
    return False


async def async_remove_entry(hass: HomeAssistant, entry: MobilityEntry) -> None:
    from homeassistant.helpers import issue_registry as ir

    await VehicleStore(hass, entry.entry_id).async_remove()
    for kind in ("source", "storage", "reset"):
        ir.async_delete_issue(hass, "mobility_forecast", f"{kind}_{entry.entry_id}")
