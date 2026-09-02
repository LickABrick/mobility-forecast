from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant

def async_track_time_interval(
    hass: HomeAssistant,
    action: Callable[[datetime], Awaitable[None]],
    interval: timedelta,
) -> Callable[[], None]: ...
