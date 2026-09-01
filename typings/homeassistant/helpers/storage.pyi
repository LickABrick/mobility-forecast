from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant

class Store[T: Mapping[str, Any]]:
    def __init__(
        self,
        hass: HomeAssistant,
        version: int,
        key: str,
        private: bool = False,
        *,
        atomic_writes: bool = False,
    ) -> None: ...
    async def async_load(self) -> T | None: ...
    async def async_save(self, data: T) -> None: ...
