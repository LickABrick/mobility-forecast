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
from .history import (
    ResettingCounterError,
    daily_distances,
    import_history,
    merge_readings,
)
from .models import Forecast, Reading, Status
from .odometer import InvalidReading, kilometers
from .storage import VehicleStore

_LOGGER = logging.getLogger(__name__)
MAX_DAY_ATTEMPTS = 3
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
        self.route_metrics = {}
        self.calendar_metrics = {}
        self.calendar_days = None
        self.calendar_pending_days = set()
        self.calendar_attempts = {}
        self.calendar_retry_at = {}
        self.calendar_publish = None
        self.calendar_publish_task = None
        self.calendar_retry = None
        self.calendar_next_work = None
        self.calendar_status = "disabled"
        self.calendar_task = None
        self.calendar_generation = 0
        self.stopping = False
        self.initialization_task = None
        self.initialized = False
        self.import_status = "pending"
        self.source_continuous = True
        self.source_incompatible = False
        self.reset_dates = set()
        self.previous_report = None
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
        except ResettingCounterError:
            self._mark_incompatible()
            self.import_status = "incompatible_source"
            await self.async_request_refresh()
            return
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
        quality = self.store.payload.get("source_quality", {})
        if quality.get("entity") == self.source:
            self.reset_dates = set(quality.get("reset_dates", []))
            if len(self.reset_dates) >= 2 or quality.get("incompatible"):
                self._mark_incompatible()
        else:
            from homeassistant.helpers import issue_registry as ir

            ir.async_delete_issue(self.hass, DOMAIN, f"reset_{self.entry.entry_id}")
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
        except ResettingCounterError:
            self._mark_incompatible()
            self.import_status = "incompatible_source"
            await self.async_request_refresh()
            return
        except Exception:
            self.import_status = "failed"
            _LOGGER.warning(
                "Historical import failed (%s); stored history preserved",
                self.entry.entry_id,
            )
            await self.async_request_refresh()
            return
        self.import_status = "complete"
        from .source_quality import reset_count

        if reset_count(incoming) >= 2:
            self._mark_incompatible()
            await self.async_request_refresh()
            return
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
        # Detect raw report decreases before monotonic validation rejects them.
        stamp = state.last_reported
        if (
            self.previous_report
            and stamp > self.previous_report.timestamp
            and km < self.previous_report.km
        ):
            self.reset_dates.add(stamp.date().isoformat())
            self.store.payload["source_quality"] = {
                "entity": self.source,
                "reset_dates": sorted(self.reset_dates)[-3:],
            }
            if len(self.reset_dates) >= 2:
                self._mark_incompatible()
        if self.previous_report is None or stamp > self.previous_report.timestamp:
            self.previous_report = Reading(stamp, km, "live", self.source)
        if self.source_incompatible:
            return
        # Unchanged reports are useful fresh brackets, capped to one per hour.
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

    def _mark_incompatible(self):
        from homeassistant.helpers import issue_registry as ir

        self.source_incompatible = True
        self.store.payload["source_quality"] = {
            "entity": self.source,
            "reset_dates": sorted(self.reset_dates),
            "incompatible": True,
        }
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"reset_{self.entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="resetting_counter",
        )

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
            if self.source_incompatible:
                forecast.status = Status.SOURCE_INCOMPATIBLE
                forecast.values = dict.fromkeys(forecast.values)
            self.store.schedule(self.readings)
            return forecast

    def _schedule_calendar(self, now):
        """Coalesce requests. No external work occurs under the history lock."""
        signature = repr(dict(self.entry.options))
        if getattr(self, "calendar_signature", None) != signature:
            self.calendar_signature = signature
            self.calendar_generation += 1
            self.calendar_refreshed_at = None
            self.calendar_days = None
            self.calendar_pending_days = set()
            self.calendar_attempts = {}
            self.calendar_retry_at = {}
            self.calendar_next_work = None
            self._cancel_calendar_publish()
            self.route_metrics = {}
            self.calendar_metrics = {}
            if self.calendar_retry:
                self.calendar_retry.cancel()
                self.calendar_retry = None
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
        continuing = (
            bool(self.calendar_pending_days)
            and self.calendar_next_work is not None
            and now >= self.calendar_next_work
            and self.calendar_refreshed_at is not None
            and (now - self.calendar_refreshed_at).total_seconds() < 1800
        )
        if (
            not continuing
            and self.calendar_refreshed_at is not None
            and (now - self.calendar_refreshed_at).total_seconds() < 1800
        ):
            return
        if not continuing:
            self.calendar_days = None
            self.calendar_refreshed_at = now
        self.calendar_status = "refreshing"
        generation = self.calendar_generation
        self.calendar_task = self.entry.async_create_background_task(
            self.hass,
            self._refresh_calendar(now, generation),
            "mobility calendar refresh",
        )

    def _calendar_current(self, generation, options):
        return (
            not self.stopping
            and generation == self.calendar_generation
            and options == dict(self.entry.options)
        )

    def _calendar_progress(self):
        self.calendar_metrics.update(
            days_complete=sum(p.complete for p in self.plans.values()),
            days_incomplete=sum(not p.complete for p in self.plans.values()),
            days_pending=len(self.calendar_pending_days),
        )

    def _cancel_calendar_publish(self):
        if self.calendar_publish:
            self.calendar_publish.cancel()
            self.calendar_publish = None

    def _queue_calendar_publish(self, generation):
        if self.calendar_publish is not None:
            return

        @callback
        def publish():
            self.calendar_publish = None
            if (
                not self.stopping
                and generation == self.calendar_generation
                and (
                    self.calendar_publish_task is None
                    or self.calendar_publish_task.done()
                )
            ):
                self.calendar_publish_task = self.entry.async_create_background_task(
                    self.hass,
                    self.async_request_refresh(),
                    "mobility calendar publication",
                )

        self.calendar_publish = self.hass.loop.call_later(2, publish)

    async def _refresh_calendar(self, now, generation):
        from .calendar_manager import (
            CalendarResponseError,
            fetch_events,
            preprocess_appointments,
        )
        from .locations import home_and_known
        from .routing import RequestBudgetExceeded, WazeProvider, _plan_journeys

        options = dict(self.entry.options)
        home, known = home_and_known(self.hass, options.get("known_locations", {}))
        stage = "calendar_fetch"
        provider = None
        try:
            async with asyncio.timeout(CALENDAR_REFRESH_BUDGET):
                if self.calendar_days is None:
                    # Retrieval failure makes the previous agenda untrusted. A
                    # prior completed day is not indefinitely valid after edits.
                    events = await fetch_events(
                        self.hass,
                        options["calendars"],
                        now.replace(hour=0, minute=0, second=0, microsecond=0),
                        now + timedelta(days=30),
                        known,
                    )
                    if not self._calendar_current(generation, options):
                        return
                    self.calendar_metrics["events_count"] = getattr(
                        events, "retrieved_count", len(events)
                    )
                    self.calendar_metrics.update(
                        events_invalid_skipped=getattr(events, "invalid_count", 0),
                        events_routable=sum(
                            not e.virtual and e.location is not None for e in events
                        ),
                        events_without_location=sum(
                            not e.virtual and e.location is None for e in events
                        ),
                        events_virtual_skipped=sum(e.virtual for e in events),
                    )
                    events, ignored = preprocess_appointments(
                        events, options.get("ignore_nested_appointments", False)
                    )
                    self.calendar_metrics.update(
                        nested_ignored=ignored,
                        relevant_count=len(events),
                        requests=0,
                        retry_exhausted=0,
                        last_failure=None,
                    )
                    grouped = {}
                    for event in events:
                        day = event.start.date()
                        while day <= event.end.date():
                            if now.date() <= day <= (
                                now + timedelta(days=30)
                            ).date() and (
                                day < event.end.date()
                                or event.end.hour
                                or event.end.minute
                                or event.end.second
                            ):
                                grouped.setdefault(day, []).append(event)
                            day += timedelta(days=1)
                    self.calendar_days = grouped
                    self.calendar_pending_days = set(grouped)
                    self.calendar_attempts = {}
                    self.calendar_retry_at = {}
                    self.plans = {}
                stage = "route_planning"
                provider = WazeProvider(
                    self.hass, options.get("region", ""), self.store.payload["routes"]
                )
                first_published = False
                queue = sorted(
                    day
                    for day in self.calendar_pending_days
                    if self.calendar_retry_at.get(day, now) <= now
                )

                async def worker():
                    nonlocal first_published
                    while queue:
                        day = queue.pop(0)
                        try:
                            results = await _plan_journeys(
                                self.calendar_days[day], home, provider
                            )
                        except RequestBudgetExceeded:
                            return
                        if not self._calendar_current(generation, options):
                            return
                        plan = results[day]
                        # Atomic day commit; never publish a partial chain.
                        self.plans[day] = plan
                        if plan.reason:
                            self.calendar_metrics["last_failure"] = plan.reason
                        if plan.retryable:
                            attempts = self.calendar_attempts.get(day, 0) + 1
                            self.calendar_attempts[day] = attempts
                            if attempts < MAX_DAY_ATTEMPTS:
                                self.calendar_retry_at[day] = (
                                    dt_util.utcnow()
                                    + timedelta(seconds=60 * 2 ** (attempts - 1))
                                )
                            else:
                                self.calendar_pending_days.discard(day)
                                self.calendar_metrics["retry_exhausted"] = sum(
                                    value >= MAX_DAY_ATTEMPTS
                                    for value in self.calendar_attempts.values()
                                )
                        else:
                            self.calendar_pending_days.discard(day)
                            self.calendar_retry_at.pop(day, None)
                        self._calendar_progress()
                        self.calendar_status = (
                            "partial" if self.calendar_pending_days else "refreshing"
                        )
                        if plan.complete and not first_published:
                            first_published = True
                            await self.async_request_refresh()
                        else:
                            self._queue_calendar_publish(generation)

                async with asyncio.TaskGroup() as tasks:
                    for _ in range(min(3, len(queue))):
                        tasks.create_task(worker())
            if not self._calendar_current(generation, options):
                return
            self._calendar_progress()
            incomplete = any(not p.complete for p in self.plans.values())
            complete = any(p.complete for p in self.plans.values())
            self.calendar_status = (
                "partial"
                if complete and (incomplete or self.calendar_pending_days)
                else "incomplete"
                if incomplete
                else "refreshing"
                if self.calendar_pending_days
                else "ready"
            )
            if provider.last_failure:
                self.calendar_metrics["last_failure"] = provider.last_failure
                if not complete and provider.last_failure != "request_budget":
                    self.calendar_status = "routing_unavailable"
            if self.calendar_status == "ready":
                self.calendar_metrics["last_success"] = dt_util.utcnow().isoformat()
                self.calendar_metrics["last_failure"] = None
        except Exception as err:
            if not self._calendar_current(generation, options):
                return
            category = (
                "refresh_timeout"
                if isinstance(err, TimeoutError)
                else "calendar_normalization"
                if isinstance(err, CalendarResponseError)
                else stage
            )
            self.calendar_metrics["last_failure"] = category
            if stage == "calendar_fetch":
                self.plans = {}
                self.calendar_days = None
                self.calendar_pending_days.clear()
            self.calendar_status = (
                "partial"
                if any(p.complete for p in self.plans.values())
                else "routing_timeout"
                if isinstance(err, TimeoutError)
                else "calendar_unavailable"
                if stage == "calendar_fetch"
                else "routing_unavailable"
            )
            _LOGGER.warning(
                "Calendar stage=%s exception=%s", category, type(err).__name__
            )
        finally:
            # Also save successful legs when the generation is cancelled or a
            # later day fails; HA storage coalesces these cycle-level writes.
            if provider:
                await provider.async_close()
                if self._calendar_current(generation, options):
                    self.route_metrics = provider.statistics
                    _LOGGER.debug(
                        "Routing cycle events=%d relevant=%d nested_ignored=%d cache_hits=%d waze_requests=%d waze_failures=%d",
                        self.calendar_metrics.get("events_count", 0),
                        self.calendar_metrics.get("relevant_count", 0),
                        self.calendar_metrics.get("nested_ignored", 0),
                        provider.statistics["route_cache_hits"],
                        provider.requests,
                        provider.failures,
                    )
                self.store.schedule_routes()
            if self._calendar_current(generation, options):
                if provider:
                    self.calendar_metrics["requests"] = (
                        self.calendar_metrics.get("requests", 0) + provider.requests
                    )
                self._calendar_progress()
                if self.calendar_pending_days:
                    # Deferred work waits >=60s; transient days use 60/120s backoff.
                    clock = dt_util.utcnow()
                    self.calendar_next_work = max(
                        clock + timedelta(seconds=60),
                        min(
                            self.calendar_retry_at.get(day, clock)
                            for day in self.calendar_pending_days
                        ),
                    )
                    delay = (self.calendar_next_work - clock).total_seconds()
                    if self.calendar_retry:
                        self.calendar_retry.cancel()
                    self.calendar_retry = self.hass.loop.call_later(
                        delay, self._refresh_later
                    )
        if self._calendar_current(generation, options):
            self._cancel_calendar_publish()
            await self.async_request_refresh()

    async def shutdown(self):
        self.stopping = True
        self._cancel_calendar_publish()
        if self.calendar_publish_task and not self.calendar_publish_task.done():
            self.calendar_publish_task.cancel()
            try:
                await self.calendar_publish_task
            except asyncio.CancelledError:
                pass
        if self.calendar_retry:
            self.calendar_retry.cancel()
            self.calendar_retry = None
        if self.initialization_task and not self.initialization_task.done():
            self.initialization_task.cancel()
            try:
                await self.initialization_task
            except asyncio.CancelledError:
                pass
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
