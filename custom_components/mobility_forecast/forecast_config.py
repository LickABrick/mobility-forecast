"""Explicit uncertainty policy owned by one forecast profile."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from .domain.actuals_forecasting import ForecastPolicy

CONF_MINIMUM_HISTORY_SAMPLES = "minimum_history_samples"
CONF_MINIMUM_CORRECTION_PERCENT = "minimum_correction_percent"
CONF_MAXIMUM_CORRECTION_PERCENT = "maximum_correction_percent"
CONF_COLD_START_P90_PERCENT = "cold_start_p90_percent"

MAXIMUM_HISTORY_SAMPLES: Final = 365
MINIMUM_CORRECTION_PERCENT: Final = 10
MAXIMUM_CORRECTION_PERCENT: Final = 300
MINIMUM_COLD_START_P90_PERCENT: Final = 100
MAXIMUM_COLD_START_P90_PERCENT: Final = 300


@dataclass(frozen=True, slots=True)
class ProfileForecastConfig:
    """JSON-safe explicit settings projected into the pure forecast model."""

    minimum_history_samples: int
    minimum_correction_percent: int
    maximum_correction_percent: int
    cold_start_p90_percent: int

    def __post_init__(self) -> None:
        if not 1 <= self.minimum_history_samples <= MAXIMUM_HISTORY_SAMPLES:
            raise ValueError("minimum history samples are unavailable")
        if not (
            MINIMUM_CORRECTION_PERCENT
            <= self.minimum_correction_percent
            <= self.maximum_correction_percent
            <= MAXIMUM_CORRECTION_PERCENT
        ):
            raise ValueError("correction percentage bounds are unavailable")
        if not (
            MINIMUM_COLD_START_P90_PERCENT
            <= self.cold_start_p90_percent
            <= MAXIMUM_COLD_START_P90_PERCENT
        ):
            raise ValueError("cold-start P90 percentage is unavailable")

    @classmethod
    def from_entry_data(cls, data: Mapping[str, object]) -> ProfileForecastConfig:
        """Decode all required values without supplying defaults."""

        return cls(
            _required_int(data, CONF_MINIMUM_HISTORY_SAMPLES),
            _required_int(data, CONF_MINIMUM_CORRECTION_PERCENT),
            _required_int(data, CONF_MAXIMUM_CORRECTION_PERCENT),
            _required_int(data, CONF_COLD_START_P90_PERCENT),
        )

    def as_entry_data(self) -> dict[str, int]:
        """Return the exact persisted schema representation."""

        return {
            CONF_MINIMUM_HISTORY_SAMPLES: self.minimum_history_samples,
            CONF_MINIMUM_CORRECTION_PERCENT: self.minimum_correction_percent,
            CONF_MAXIMUM_CORRECTION_PERCENT: self.maximum_correction_percent,
            CONF_COLD_START_P90_PERCENT: self.cold_start_p90_percent,
        }

    @property
    def forecast_policy(self) -> ForecastPolicy:
        """Project percentages into explicit model ratios."""

        return ForecastPolicy(
            minimum_history_samples=self.minimum_history_samples,
            minimum_correction_ratio=self.minimum_correction_percent / 100,
            maximum_correction_ratio=self.maximum_correction_percent / 100,
            cold_start_p90_multiplier=self.cold_start_p90_percent / 100,
        )


def _required_int(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} is unavailable")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{key} is unavailable")
