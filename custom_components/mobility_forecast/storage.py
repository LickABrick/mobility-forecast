"""Versioned per-entry atomic persistence with delayed writes."""

from datetime import datetime

from homeassistant.helpers.storage import Store

from .const import DOMAIN, MAX_READINGS
from .history import merge_readings
from .models import Reading


class VehicleStore(Store):
    def __init__(self, hass, entry_id):
        super().__init__(hass, 1, f"{DOMAIN}.{entry_id}")
        self.payload = {"readings": [], "routes": {}, "evaluation": {}, "snapshots": {}}
        self.corrupt = False

    async def load_readings(self):
        try:
            data = await self.async_load()
            if data:
                self.payload.update(data)
            values = [
                Reading(datetime.fromisoformat(row[0]), float(row[1]), row[2], row[3])
                for row in self.payload["readings"][-MAX_READINGS:]
            ]
            return merge_readings([], values)[0]
        except (ValueError, TypeError, KeyError, IndexError):
            self.corrupt = True
            return []

    def schedule(self, readings):
        if self.corrupt:
            return  # never overwrite unreadable user data
        self.payload["readings"] = [
            [r.timestamp.isoformat(), r.km, r.source, r.entity_id] for r in readings
        ]
        self.async_delay_save(lambda: self.payload, 30)

    async def flush(self):
        if not self.corrupt:
            await self.async_save(self.payload)
