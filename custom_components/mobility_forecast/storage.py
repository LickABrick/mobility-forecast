"""Versioned per-entry atomic persistence with delayed writes."""

from datetime import datetime

from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .history import merge_readings
from .models import Reading


class VehicleStore(Store):
    def __init__(self, hass, entry_id):
        super().__init__(hass, 1, f"{DOMAIN}.{entry_id}")
        self.payload = {"readings": [], "routes": {}, "evaluation": {}, "snapshots": {}}
        self.corrupt = False
        self.last_scheduled = None

    async def load_readings(self):
        try:
            data = await self.async_load()
            if data is not None:
                if (
                    not isinstance(data, dict)
                    or not isinstance(data.get("readings", []), list)
                    or any(
                        not isinstance(data.get(key, {}), dict)
                        for key in ("routes", "evaluation", "snapshots")
                    )
                ):
                    raise ValueError("Invalid vehicle storage structure")
                self.payload.update(data)
                from .comparison import migrate_snapshots

                self.payload["snapshots"] = migrate_snapshots(self.payload["snapshots"])
            values = [
                Reading(datetime.fromisoformat(row[0]), float(row[1]), row[2], row[3])
                for row in self.payload["readings"]
            ]
            accepted, rejected = merge_readings([], values)
            if rejected:
                raise ValueError("Invalid persisted samples; preserve original file")
            return accepted
        except (ValueError, TypeError, KeyError, IndexError):
            self.corrupt = True
            return []

    def schedule(self, readings):
        if self.corrupt:
            return  # never overwrite unreadable user data
        self.payload["readings"] = [
            [r.timestamp.isoformat(), r.km, r.source, r.entity_id] for r in readings
        ]
        import copy

        if self.payload == self.last_scheduled:
            return
        self.last_scheduled = copy.deepcopy(self.payload)
        self.async_delay_save(lambda: self.payload, 30)

    def schedule_routes(self):
        """Debounce cache persistence without reserializing odometer history."""
        if not self.corrupt:
            self.async_delay_save(lambda: self.payload, 30)

    async def flush(self):
        if not self.corrupt:
            await self.async_save(self.payload)
