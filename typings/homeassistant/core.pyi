from collections.abc import Mapping
from typing import Any

from .config_entries import ConfigEntries

class HomeAssistant:
    config_entries: ConfigEntries
    data: Mapping[object, Any]
