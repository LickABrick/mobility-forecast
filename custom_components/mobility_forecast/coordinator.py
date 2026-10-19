"""Independent vehicle state, debounced ingestion and periodic recalculation."""

import asyncio
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .forecasting import evaluate, predict
from .history import daily_distances, import_history, merge_readings
from .models import Reading, Status
from .odometer import InvalidReading, kilometers
from .storage import VehicleStore

_LOGGER = logging.getLogger(__name__)


class VehicleCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=30),
        )
        self.entry = entry
        self.source = entry.data["odometer"]
        self.readings = []
        self.store = VehicleStore(hass, entry.entry_id)
        self.lock = asyncio.Lock()
        self.rejected = 0
        self.pending = None
        self.import_task = None
        self.source_available = False
        self.plans = {}
        self.calendar_status = "disabled"

    async def initialize(self):
        self.readings = await self.store.load_readings()
        registry_id = self.entry.data.get("registry_id")
        if registry_id:
            entity = next(
                (
                    item
                    for item in er.async_get(self.hass).entities.values()
                    if item.id == registry_id
                ),
                None,
            )
            if entity:
                self.source = entity.entity_id
        self.entry.async_on_unload(
            async_track_state_change_event(self.hass, [self.source], self._changed)
        )
        self._ingest(self.hass.states.get(self.source))
        await self.async_refresh()
        self.import_task = self.entry.async_create_background_task(
            self.hass, self._import(), "mobility history import"
        )

    async def _import(self):
        incoming = await import_history(
            self.hass,
            self.source,
            dt_util.utcnow(),
            self.readings[-1].timestamp - timedelta(days=1) if self.readings else None,
        )
        async with self.lock:
            self.readings, rejected = merge_readings(self.readings, incoming)
            self.rejected += rejected
            self.store.schedule(self.readings)
        await self.async_request_refresh()

    def _ingest(self, state):
        self.source_available = state is not None and state.state not in (
            "unknown",
            "unavailable",
        )
        if not self.source_available:
            return
        try:
            km = kilometers(state.state, state.attributes.get("unit_of_measurement"))
        except InvalidReading:
            self.source_available = False
            return
        # Unchanged reports are useful fresh brackets, capped to one per hour.
        stamp = state.last_reported
        if (
            self.readings
            and km == self.readings[-1].km
            and (stamp - self.readings[-1].timestamp).total_seconds() < 3600
        ):
            return
        self.readings, rejected = merge_readings(
            self.readings, [Reading(stamp, km, "live", self.source)]
        )
        self.rejected += rejected
        self.store.schedule(self.readings)

    @callback
    def _changed(self, event):
        self._ingest(event.data.get("new_state"))
        if self.pending is None:
            self.pending = self.hass.loop.call_later(60, self._refresh_later)

    @callback
    def _refresh_later(self):
        self.pending = None
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self):
        async with self.lock:
            zone = ZoneInfo(self.hass.config.time_zone)
            now = dt_util.utcnow().astimezone(zone)
            await self._refresh_calendar(now)
            history = daily_distances(self.readings, zone)
            forecast = predict(history, now, self.plans)
            snapshots = self.store.payload["snapshots"]
            self.store.payload["evaluation"] = evaluate(snapshots, history)
            if forecast.values["today"] is not None:
                snapshots.setdefault(now.date().isoformat(), forecast.values["today"])
            self.store.payload["snapshots"] = dict(sorted(snapshots.items())[-90:])
            if not self.source_available:
                forecast.status = Status.SOURCE_UNAVAILABLE
            if (
                self.readings
                and (now - self.readings[-1].timestamp).total_seconds() > 7 * 86400
            ):
                forecast.values = dict.fromkeys(forecast.values)
                forecast.status = Status.SOURCE_UNAVAILABLE
            self.store.schedule(self.readings)
            return forecast

    async def _refresh_calendar(self, now):
        from .calendar_manager import fetch_events
        from .locations import home_and_known
        from .routing import WazeProvider, plan_journeys

        calendars = self.entry.options.get("calendars", [])
        if not calendars:
            self.plans = {}
            self.calendar_status = "disabled"
            return
        home, known = home_and_known(
            self.hass, self.entry.options.get("known_locations", {})
        )
        if not self.entry.options.get("routing", False):
            self.plans = {}
            self.calendar_status = "routing_disabled"
            return
        try:
            events = await fetch_events(
                self.hass,
                calendars,
                now.replace(hour=0, minute=0, second=0, microsecond=0),
                now + timedelta(days=30),
                known,
            )
            provider = WazeProvider(
                self.hass,
                self.entry.options.get("region", ""),
                self.store.payload["routes"],
            )
            self.plans = await plan_journeys(events, home, provider)
            self.calendar_status = (
                "incomplete"
                if any(not p.complete for p in self.plans.values())
                else "ready"
            )
            if not self.hass.services.has_service(
                "waze_travel_time", "get_travel_times"
            ):
                self.calendar_status = "routing_unavailable"
        except Exception:
            self.plans = {}
            self.calendar_status = "calendar_unavailable"

    async def shutdown(self):
        if self.pending:
            self.pending.cancel()
        if self.import_task and not self.import_task.done():
            self.import_task.cancel()
            try:
                await self.import_task
            except asyncio.CancelledError:
                pass
        await self.store.flush()
        await self.async_shutdown()
