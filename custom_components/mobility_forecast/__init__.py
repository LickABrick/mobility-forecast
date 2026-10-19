"""Mobility Forecast entry lifecycle."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


@dataclass
class Runtime:
    source: str


type MobilityEntry = ConfigEntry[Runtime]


async def async_setup_entry(hass: HomeAssistant, entry: MobilityEntry) -> bool:
    entry.runtime_data = Runtime(entry.data["odometer"])
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Mobility Forecast",
        model="Distance forecast",
    )
    entry.async_on_unload(entry.add_update_listener(async_reload))
    return True


async def async_reload(hass: HomeAssistant, entry: MobilityEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MobilityEntry) -> bool:
    return True
