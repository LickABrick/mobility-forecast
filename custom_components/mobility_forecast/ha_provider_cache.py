"""Private atomic Home Assistant storage for one profile's provider caches."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .domain.models import Coordinates, Route
from .domain.routing import RouteCacheEntry, RouteCacheKey
from .openrouteservice import GeocodeCacheEntry
from .provider_cache_storage import (
    PRIVACY_KEY_BYTES,
    PROVIDER_CACHE_STORAGE_SCHEMA_VERSION,
    ProviderCacheState,
    decode_provider_cache_state,
    encode_provider_cache_state,
    provider_cache_storage_key,
    prune_provider_cache_state,
)
from .provider_guardrails import GeocodeCacheKey

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _generate_privacy_key() -> bytes:
    return secrets.token_bytes(PRIVACY_KEY_BYTES)


class _PersistentGeocodeCache:
    def __init__(self, owner: HomeAssistantProviderCaches) -> None:
        self._owner = owner

    async def get(self, key: GeocodeCacheKey) -> GeocodeCacheEntry | None:
        return await self._owner.get_geocode(key)

    async def put(
        self, key: GeocodeCacheKey, coordinates: Coordinates, stored_at: datetime
    ) -> None:
        await self._owner.put_geocode(key, coordinates, stored_at)

    async def delete(self, key: GeocodeCacheKey) -> None:
        await self._owner.delete_geocode(key)


class _PersistentRouteCache:
    def __init__(self, owner: HomeAssistantProviderCaches) -> None:
        self._owner = owner

    async def get(self, key: RouteCacheKey) -> RouteCacheEntry | None:
        return await self._owner.get_route(key)

    async def put(self, key: RouteCacheKey, route: Route, stored_at: datetime) -> None:
        await self._owner.put_route(key, route, stored_at)

    async def delete(self, key: RouteCacheKey) -> None:
        await self._owner.delete_route(key)


class HomeAssistantProviderCaches:
    """Own a privacy key and both persistent caches for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        *,
        generate_privacy_key: Callable[[], bytes] = _generate_privacy_key,
    ) -> None:
        self._store = Store[dict[str, object]](
            hass,
            PROVIDER_CACHE_STORAGE_SCHEMA_VERSION,
            provider_cache_storage_key(config_entry_id),
            private=True,
            atomic_writes=True,
        )
        self._generate_privacy_key = generate_privacy_key
        self._state: ProviderCacheState | None = None
        self._lock = asyncio.Lock()
        self.geocode_cache = _PersistentGeocodeCache(self)
        self.route_cache = _PersistentRouteCache(self)

    @property
    def privacy_key(self) -> bytes:
        """Return initialized profile-local HMAC key material."""

        return self._require_state().privacy_key

    async def async_initialize(
        self,
        *,
        evaluated_at: datetime,
        maximum_geocode_age: timedelta,
        maximum_route_age: timedelta,
    ) -> None:
        """Restore state or create a key, then prune all retained entries."""

        async with self._lock:
            if self._state is not None:
                raise RuntimeError("provider caches are already initialized")
            payload = await self._store.async_load()
            if payload is None:
                state = ProviderCacheState(self._generate_privacy_key(), (), ())
                await self._store.async_save(encode_provider_cache_state(state))
                self._state = state
                return

            restored = decode_provider_cache_state(payload)
            pruned = prune_provider_cache_state(
                restored,
                evaluated_at=evaluated_at,
                maximum_geocode_age=maximum_geocode_age,
                maximum_route_age=maximum_route_age,
            )
            if pruned != restored:
                await self._store.async_save(encode_provider_cache_state(pruned))
            self._state = pruned

    async def async_rotate_privacy_key(self) -> bytes:
        """Replace key material and atomically discard both dependent caches."""

        async with self._lock:
            self._require_state()
            next_state = ProviderCacheState(self._generate_privacy_key(), (), ())
            await self._store.async_save(encode_provider_cache_state(next_state))
            self._state = next_state
            return next_state.privacy_key

    def _require_state(self) -> ProviderCacheState:
        if self._state is None:
            raise RuntimeError("provider caches are not initialized")
        return self._state

    async def _save(self, state: ProviderCacheState) -> None:
        await self._store.async_save(encode_provider_cache_state(state))
        self._state = state

    async def get_geocode(self, key: GeocodeCacheKey) -> GeocodeCacheEntry | None:
        async with self._lock:
            return dict(self._require_state().geocodes).get(key)

    async def put_geocode(
        self, key: GeocodeCacheKey, coordinates: Coordinates, stored_at: datetime
    ) -> None:
        async with self._lock:
            state = self._require_state()
            entries = dict(state.geocodes)
            entries[key] = GeocodeCacheEntry(coordinates, stored_at)
            await self._save(
                ProviderCacheState(
                    state.privacy_key,
                    tuple(sorted(entries.items(), key=lambda item: item[0].digest)),
                    state.routes,
                )
            )

    async def delete_geocode(self, key: GeocodeCacheKey) -> None:
        async with self._lock:
            state = self._require_state()
            entries = dict(state.geocodes)
            if entries.pop(key, None) is None:
                return
            await self._save(
                ProviderCacheState(
                    state.privacy_key,
                    tuple(sorted(entries.items(), key=lambda item: item[0].digest)),
                    state.routes,
                )
            )

    async def get_route(self, key: RouteCacheKey) -> RouteCacheEntry | None:
        async with self._lock:
            return dict(self._require_state().routes).get(key)

    async def put_route(
        self, key: RouteCacheKey, route: Route, stored_at: datetime
    ) -> None:
        async with self._lock:
            state = self._require_state()
            entries = dict(state.routes)
            entries[key] = RouteCacheEntry(route, stored_at)
            await self._save(
                ProviderCacheState(
                    state.privacy_key,
                    state.geocodes,
                    tuple(sorted(entries.items(), key=lambda item: item[0].digest)),
                )
            )

    async def delete_route(self, key: RouteCacheKey) -> None:
        async with self._lock:
            state = self._require_state()
            entries = dict(state.routes)
            if entries.pop(key, None) is None:
                return
            await self._save(
                ProviderCacheState(
                    state.privacy_key,
                    state.geocodes,
                    tuple(sorted(entries.items(), key=lambda item: item[0].digest)),
                )
            )
