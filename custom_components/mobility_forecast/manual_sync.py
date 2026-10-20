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

    async def request(self):
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
        await asyncio.shield(self.task)

    async def run(self):
        try:
            # At most two passes per burst. Continuous triggers cannot keep the
            # switch busy indefinitely or grow a queue without bound.
            for _ in range(2):
                self.again = False
                async with asyncio.timeout(120):
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
