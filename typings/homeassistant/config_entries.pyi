from typing import Any

class ConfigEntry[RuntimeT]:
    entry_id: str
    runtime_data: RuntimeT | None

class ConfigEntries:
    async def async_forward_entry_setups(
        self, entry: ConfigEntry[Any], platforms: tuple[str, ...]
    ) -> None: ...
    async def async_unload_platforms(
        self, entry: ConfigEntry[Any], platforms: tuple[str, ...]
    ) -> bool: ...
