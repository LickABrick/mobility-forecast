"""Config-entry-scoped Home Assistant Store adapter for private profile state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .storage import (
    STORAGE_SCHEMA_VERSION,
    ProfileState,
    decode_profile_state,
    encode_profile_state,
    profile_storage_key,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_EMPTY_PROFILE_STATE = ProfileState((), (), ())


class HomeAssistantProfileStorage:
    """Persist one profile through Home Assistant's private atomic Store helper."""

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        self._config_entry_id = config_entry_id
        self._store = Store[dict[str, object]](
            hass,
            STORAGE_SCHEMA_VERSION,
            profile_storage_key(config_entry_id),
            private=True,
            atomic_writes=True,
        )

    def _validate_entry(self, config_entry_id: str) -> None:
        if config_entry_id != self._config_entry_id:
            raise ValueError("config entry mismatch for profile storage")

    async def load(self, config_entry_id: str) -> ProfileState:
        """Load this entry's state, using an empty state only when no store exists."""

        self._validate_entry(config_entry_id)
        payload = await self._store.async_load()
        if payload is None:
            return _EMPTY_PROFILE_STATE
        return decode_profile_state(payload)

    async def save(self, config_entry_id: str, state: ProfileState) -> None:
        """Persist validated state under this entry's private storage key."""

        self._validate_entry(config_entry_id)
        await self._store.async_save(encode_profile_state(state))
