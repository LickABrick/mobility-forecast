"""One owned manual task per vehicle; repeat requests queue at most one follow-up.

Off is runtime idle, never a cancellation command. No state is restored on reload.
A round performs bounded work, not an exhaustive calendar or charger crawl.
"""

import asyncio

from homeassistant.util import dt as dt_util


class ManualSync:
    def __init__(self, owner, cycle):
        self.owner = owner
        self.cycle = cycle
        self.task = None
        self.running = False
        self.stopping = False
        self.again = False
        self.status = "idle"
        self.error = None
        self.requested_at = None
        self.started_at = None
        self.finished_at = None
        self.listeners = []

    def publish(self):
        for listener in tuple(self.listeners):
            listener()

    def trigger(self):
        if self.stopping:
            return
        self.requested_at = dt_util.utcnow()
        if self.task and not self.task.done():
            self.again = True
        else:
            self.running = True
            self.status = "running"
            self.error = None
            self.started_at = dt_util.utcnow()
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
            # One shared deadline bounds the whole burst. Only one dirty bit is
            # queued; a request during a follow-up is not silently dropped.
            async with asyncio.timeout(120):
                while True:
                    self.again = False
                    await self.cycle()
                    if not self.again:
                        break
            self.status = "success"
        except asyncio.CancelledError:
            self.status = "interrupted"
            raise
        except Exception:
            self.status = "error"
            self.error = "sync_failed"
        finally:
            self.running = False
            self.finished_at = dt_util.utcnow()
            self.publish()

    async def close(self):
        self.stopping = True
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
