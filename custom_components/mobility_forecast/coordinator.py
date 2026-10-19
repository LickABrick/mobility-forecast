"""Independent vehicle state, debounced ingestion and periodic recalculation."""

import asyncio
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FORECAST_KEYS
from .forecasting import evaluate, predict
from .history import daily_distances, import_history, merge_readings
from .models import Forecast, Reading, Status
from .odometer import InvalidReading, kilometers
from .storage import VehicleStore

_LOGGER = logging.getLogger(__name__)
CALENDAR_REFRESH_BUDGET = 45  # seconds, includes retrieval and all route legs


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
        self.calendar_task = None
        self.calendar_generation = 0
        self.stopping = False
        self.initialization_task = None
        self.initialized = False
        self.import_status = "pending"
        self.source_continuous = True
        self.async_set_updated_data(
            Forecast(
                dt_util.utcnow(), Status.INITIALIZING, dict.fromkeys(FORECAST_KEYS)
            )
        )

    def start_initialization(self):
        self.initialization_task = self.entry.async_create_background_task(
            self.hass, self._initialize_safely(), "mobility initialization"
        )

    async def _initialize_safely(self):
        try:
            await self.initialize()
        except Exception:
            self.import_status = "failed"
            # Do not log exception contents: upstream errors may contain private data.
            _LOGGER.error(
                "Vehicle initialization failed (%s); forecast entities remain registered",
                self.entry.entry_id,
            )
            self.async_set_updated_data(
                Forecast(dt_util.utcnow(), Status.ERROR, dict.fromkeys(FORECAST_KEYS))
            )

    async def initialize(self):
        self.readings = await self.store.load_readings()
        # Capture the import watermark BEFORE ingesting current state. Otherwise a
        # first installation imports only yesterday instead of available history.
        self.import_since = (
            self.readings[-1].timestamp - timedelta(days=1) if self.readings else None
        )
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
        self.entry.async_on_unload(
            async_track_time_change(
                self.hass, self._midnight, hour=0, minute=0, second=1
            )
        )
        from homeassistant.helpers import issue_registry as ir

        if self.store.corrupt:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"storage_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="storage",
            )
        if self.hass.states.get(self.source) is None:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"source_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="source",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, f"source_{self.entry.entry_id}")
        current = self.hass.states.get(self.source)
        self.source_continuous = True
        if (
            self.readings
            and self.readings[-1].entity_id
            and self.readings[-1].entity_id != self.source
            and current is not None
        ):
            try:
                current_km = kilometers(
                    current.state, current.attributes.get("unit_of_measurement")
                )
                elapsed = max(
                    0,
                    (
                        current.last_reported - self.readings[-1].timestamp
                    ).total_seconds()
                    / 3600,
                )
                self.source_continuous = (
                    0 <= current_km - self.readings[-1].km <= max(2, elapsed * 240)
                )
            except InvalidReading:
                self.source_continuous = False
            if not self.source_continuous:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"source_{self.entry.entry_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="source",
                )
        if self.source_continuous:
            self._ingest(current)
        self.initialized = True
        await self.async_refresh()
        self.import_task = self.entry.async_create_background_task(
            self.hass, self._import(), "mobility history import"
        )

    async def _import(self):
        if not self.source_continuous:
            return
        self.import_status = "importing"
        try:
            incoming = await import_history(
                self.hass, self.source, dt_util.utcnow(), self.import_since
            )
        except Exception:
            self.import_status = "failed"
            _LOGGER.warning(
                "Historical import failed (%s); stored history preserved",
                self.entry.entry_id,
            )
            await self.async_request_refresh()
            return
        self.import_status = "complete"
        async with self.lock:
            self.readings, rejected = merge_readings(self.readings, incoming)
            self.rejected += rejected
            self.store.schedule(self.readings)
        await self.async_request_refresh()

    def _ingest(self, state):
        if not getattr(self, "source_continuous", True):
            return
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
        reading = Reading(stamp, km, "live", self.source)
        if self.readings and stamp > self.readings[-1].timestamp:
            last = self.readings[-1]
            elapsed = (stamp - last.timestamp).total_seconds() / 3600
            delta = km - last.km
            if delta < 0 or delta > max(2, elapsed * 240):
                self.rejected += 1
                return
            hour = int(stamp.timestamp()) // 3600
            if len(self.readings) >= 2 and all(
                int(r.timestamp.timestamp()) // 3600 == hour for r in self.readings[-2:]
            ):
                self.readings[-1] = reading
            else:
                self.readings.append(reading)
        else:
            self.readings, rejected = merge_readings(self.readings, [reading])
            self.rejected += rejected
        # Forecast debounce persists the coalesced data; no whole-store copy for
        # every high-frequency telemetry event.

    @callback
    def _changed(self, event):
        self._ingest(event.data.get("new_state"))
        if self.pending is None:
            self.pending = self.hass.loop.call_later(60, self._refresh_later)

    async def _midnight(self, now):
        await self.async_request_refresh()

    @callback
    def _refresh_later(self):
        self.pending = None
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self):
        async with self.lock:
            zone = ZoneInfo(self.hass.config.time_zone)
            now = dt_util.utcnow().astimezone(zone)
            # A periodic read only uses last_reported, never advances a stale state.
            self._ingest(self.hass.states.get(self.source))
            self._schedule_calendar(now)
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

    def _schedule_calendar(self, now):
        """Coalesce requests. No external work occurs under the history lock."""
        signature = repr(dict(self.entry.options))
        if getattr(self, "calendar_signature", None) != signature:
            self.calendar_signature = signature
            self.calendar_generation += 1
            self.calendar_refreshed_at = None
            self.plans = {}
            if self.calendar_task and not self.calendar_task.done():
                self.calendar_task.cancel()
        if self.stopping:
            return
        if not self.entry.options.get("calendars") or not self.entry.options.get(
            "routing"
        ):
            self.calendar_status = "disabled"
            self.plans = {}
            return
        if self.calendar_task and not self.calendar_task.done():
            return
        if (
            self.calendar_refreshed_at is not None
            and (now - self.calendar_refreshed_at).total_seconds() < 1800
        ):
            return
        self.calendar_refreshed_at = now
        self.calendar_status = "refreshing"
        generation = self.calendar_generation
        self.calendar_task = self.entry.async_create_background_task(
            self.hass,
            self._refresh_calendar(now, generation),
            "mobility calendar refresh",
        )

    async def _refresh_calendar(self, now, generation):
        from .calendar_manager import fetch_events
        from .locations import home_and_known
        from .routing import WazeProvider, plan_journeys

        options = dict(self.entry.options)
        home, known = home_and_known(self.hass, options.get("known_locations", {}))
        try:
            # Whole refresh budget includes calendars AND every route leg.
            async with asyncio.timeout(CALENDAR_REFRESH_BUDGET):
                events = await fetch_events(
                    self.hass,
                    options["calendars"],
                    now.replace(hour=0, minute=0, second=0, microsecond=0),
                    now + timedelta(days=30),
                    known,
                )
                provider = WazeProvider(
                    self.hass, options.get("region", ""), self.store.payload["routes"]
                )
                plans = await plan_journeys(events, home, provider)
            if (
                self.stopping
                or generation != self.calendar_generation
                or options != dict(self.entry.options)
            ):
                return
            self.plans = plans
            self.calendar_status = (
                "incomplete" if any(not p.complete for p in plans.values()) else "ready"
            )
        except Exception:
            if generation != self.calendar_generation or self.stopping:
                return
            # Remove stale agenda overlays, not the usable historical model.
            self.plans = {}
            self.calendar_status = "routing_unavailable"
            _LOGGER.debug(
                "Calendar refresh failed; historical forecasts remain available"
            )
        if not self.stopping:
            await self.async_request_refresh()

    async def shutdown(self):
        self.stopping = True
        self.calendar_generation += 1
        if self.calendar_task and not self.calendar_task.done():
            self.calendar_task.cancel()
            try:
                await self.calendar_task
            except asyncio.CancelledError:
                pass
        if self.pending:
            self.pending.cancel()
        if self.import_task and not self.import_task.done():
            self.import_task.cancel()
            try:
                await self.import_task
            except asyncio.CancelledError:
                pass
        if self.initialization_task and not self.initialization_task.done():
            self.initialization_task.cancel()
            try:
                await self.initialization_task
            except asyncio.CancelledError:
                pass
        # Never overwrite disk with an empty payload if loading was interrupted.
        if self.initialized:
            self.store.schedule(self.readings)
            await self.store.flush()
        await self.async_shutdown()
