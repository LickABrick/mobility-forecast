"""One bounded owned job per vehicle; idle activity is separate from last result."""

import asyncio
from dataclasses import dataclass

from homeassistant.util import dt as dt_util

SYNC_TIMEOUT = 120


class SyncFailure(Exception):
    """A finite privacy-safe category, never external exception text."""

    def __init__(self, code):
        self.code = code


@dataclass(frozen=True)
class SyncOutcome:
    result: str = "success"
    code: str | None = None


class ManualSync:
    def __init__(self, owner, cycle):
        self.owner = owner
        self.cycle = cycle
        self.task = None
        self.running = False
        self.stopping = False
        self.again = False
        self.status = "idle"  # Compatibility with the original switch attributes.
        self.last_result = "never_run"
        self.phase = None
        self.error = None
        self.requested_at = None
        self.started_at = None
        self.finished_at = None
        self.successful_at = None
        self.duration_seconds = None
        self.listeners = []

    @property
    def activity(self):
        return "syncing" if self.running else "idle"

    def publish(self):
        for listener in tuple(self.listeners):
            listener()

    def set_phase(self, phase):
        if self.phase != phase:
            self.phase = phase
            self.publish()

    def restore(self, payload):
        """Restore only a valid completed success, never an in-flight activity."""
        value = payload.get("last_successful_sync")
        if not isinstance(value, str):
            return
        stamp = dt_util.parse_datetime(value)
        if stamp is not None and stamp.tzinfo is not None and stamp <= dt_util.utcnow():
            self.successful_at = stamp
            self.publish()

    def trigger(self):
        if self.stopping:
            return None
        self.requested_at = dt_util.utcnow()
        if self.task and not self.task.done():
            self.again = True
            self.publish()
        else:
            self.running = True
            self.status = "running"
            self.error = None
            self.started_at = dt_util.utcnow()
            self.duration_seconds = None
            self.phase = "initializing"
            self.publish()
            self.task = self.owner.hass.async_create_task(
                self.run(), "Mobility manual sync"
            )
        return self.task

    async def request(self):
        task = self.trigger()
        if task:
            await asyncio.shield(task)

    async def run(self):
        try:
            # One deadline for every coalesced round, including new requests
            # during a follow-up. No awaits between checking dirty and completion.
            incomplete = None
            async with asyncio.timeout(SYNC_TIMEOUT):
                while True:
                    self.again = False
                    outcome = await self.cycle() or SyncOutcome()
                    # A later successful round must not erase known deferred work
                    # from an earlier round in the same requested burst.
                    if outcome.result != "success":
                        incomplete = outcome
                    if not self.again:
                        break
                self.set_phase("finalizing")
            outcome = incomplete or outcome
            self.last_result = outcome.result
            self.error = outcome.code
        except asyncio.CancelledError:
            self.last_result = "interrupted"
            self.error = "sync_interrupted"
            raise
        except TimeoutError:
            self.last_result = "error"
            self.error = "sync_timeout"
        except SyncFailure as err:
            self.last_result = "error"
            self.error = err.code
        except Exception:
            self.last_result = "error"
            self.error = "sync_failed"
        finally:
            self.running = False
            self.again = False
            self.phase = None
            self.status = self.last_result
            self.finished_at = dt_util.utcnow()
            self.duration_seconds = round(
                (self.finished_at - self.started_at).total_seconds(), 3
            )
            if self.last_result == "success":
                self.successful_at = self.finished_at
                store = getattr(self.owner, "store", None)
                if store is not None:
                    store.payload["last_successful_sync"] = (
                        self.successful_at.isoformat()
                    )
                    store.schedule_routes()
            self.publish()

    async def close(self):
        self.stopping = True
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
