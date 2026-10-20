"""Bounded async HTTP, per-vehicle hashed caches, no raw queries persisted."""

import asyncio
import hashlib
import json
import time

from homeassistant.helpers.aiohttp_client import async_get_clientsession


class ProviderError(Exception):
    """Safe categorical failure; never include server bodies/addresses."""


class HTTP:
    def __init__(self, hass, cache):
        self.session = async_get_clientsession(hass)
        self.cache = cache
        self.lock = asyncio.Lock()
        self.next_request = 0.0
        self.requests = 0
        self.hits = 0
        self.cooldown = 0.0

    async def get(self, url, params, ttl):
        key = hashlib.sha256(
            (url + json.dumps(params, sort_keys=True)).encode()
        ).hexdigest()
        async with self.lock:
            now = time.time()
            self.cache = {
                k: v
                for k, v in self.cache.items()
                if isinstance(v, dict) and v.get("expires", 0) > now
            }
            cached = self.cache.get(key)
            if cached:
                self.hits += 1
                return cached["value"]
            if now < self.cooldown:
                raise ProviderError("provider_backoff")
            await asyncio.sleep(max(0, self.next_request - time.monotonic()))
            self.next_request = time.monotonic() + 1
            self.requests += 1
            try:
                async with (
                    asyncio.timeout(8),
                    self.session.get(
                        url,
                        params=params,
                        headers={
                            "User-Agent": "MobilityForecast/EV (Home Assistant; github.com/LickABrick/mobility-forecast)"
                        },
                    ) as response,
                ):
                    if response.status == 429:
                        self.cooldown = now + 300
                        raise ProviderError("provider_rate_limited")
                    if response.status != 200:
                        raise ProviderError("provider_unavailable")
                    raw = await response.content.read(512001)
                    if len(raw) > 512000:
                        raise ProviderError("provider_response_too_large")
                    return json.loads(raw)
            except (TimeoutError, OSError, ValueError) as err:
                raise ProviderError("provider_unavailable") from err

    def put(self, key, value, ttl):
        now = time.time()
        self.cache[key] = {"expires": now + ttl, "value": value}
        while len(self.cache) > 128:
            self.cache.pop(next(iter(self.cache)))


def cache_key(url, params):
    return hashlib.sha256(
        (url + json.dumps(params, sort_keys=True)).encode()
    ).hexdigest()
