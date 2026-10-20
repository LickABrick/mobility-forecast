"""Pure, timezone-aware domain objects. Distances are always kilometers."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class Status(StrEnum):
    INITIALIZING = "initializing"
    LEARNING = "learning"
    CALENDAR_ONLY = "calendar_only"
    PROVISIONAL = "provisional"
    READY = "ready"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_INCOMPATIBLE = "source_incompatible"
    ERROR = "error"


@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    km: float
    source: str = "live"
    entity_id: str = ""


@dataclass(frozen=True)
class DailyDistance:
    day: date
    km: float | None
    quality: str
    coverage: float = 0.0
    minimum_km: float = 0.0
    weekday_km: float | None = None
    weekday_weight: float = 0.0


@dataclass(frozen=True)
class DailyForecast:
    day: date
    baseline_km: float | None
    total_km: float | None
    low_km: float | None
    high_km: float | None
    planned_km: float | None = None
    calendar_complete: bool = True


@dataclass
class Forecast:
    generated_at: datetime
    status: Status
    values: dict[str, float | None]
    days: list[DailyForecast] = field(default_factory=list)
    history_days: int = 0
    quality: str = "insufficient"
