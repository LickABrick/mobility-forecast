from collections.abc import Mapping
from typing import Any

class ConfigEntry[RuntimeT]:
    entry_id: str
    data: Mapping[str, Any]
    version: int
    minor_version: int
    runtime_data: RuntimeT | None

class ConfigEntries:
    def async_update_entry(
        self,
        entry: ConfigEntry[Any],
        *,
        data: Mapping[str, Any],
        minor_version: int,
    ) -> bool: ...
    async def async_forward_entry_setups(
        self, entry: ConfigEntry[Any], platforms: tuple[str, ...]
    ) -> None: ...
    async def async_unload_platforms(
        self, entry: ConfigEntry[Any], platforms: tuple[str, ...]
    ) -> bool: ...
