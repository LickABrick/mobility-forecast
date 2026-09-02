from collections.abc import Mapping
from typing import Any

from .config_entries import ConfigEntries

class State:
    attributes: Mapping[str, Any]

class StateMachine:
    def get(self, entity_id: str) -> State | None: ...

class HomeAssistant:
    config_entries: ConfigEntries
    data: Mapping[object, Any]
    states: StateMachine
