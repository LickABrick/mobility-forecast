"""Read-only Home Assistant sensor projection for one forecast profile.

The adapter exposes only the earliest immutable coordinator forecast. It has no
polling, service, refresh, provider, vehicle, or notification capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CoordinatorSnapshot, ProfileCoordinator
from .domain.models import Forecast
from .runtime import ProfileRuntimeData


def _kilometres(distance_m: int | None) -> float | None:
    return None if distance_m is None else distance_m / 1000


class ForecastDistanceSensor(SensorEntity):
    """Expose the conservative distance forecast without initiating updates."""

    _attr_has_entity_name = True

    def __init__(
        self, config_entry_id: str, coordinator: ProfileCoordinator
    ) -> None:
        if not config_entry_id.strip():
            raise ValueError("config_entry_id must not be empty")
        self._config_entry_id = config_entry_id
        self._coordinator = coordinator

    @property
    def unique_id(self) -> str:
        """Return an entry-scoped stable identifier."""

        return f"{self._config_entry_id}_forecast_distance"

    @property
    def translation_key(self) -> str:
        """Return the reviewed entity translation key."""

        return "forecast_distance"

    @property
    def native_unit_of_measurement(self) -> str:
        """Express forecast distances in kilometres."""

        return UnitOfLength.KILOMETERS

    @property
    def _snapshot(self) -> CoordinatorSnapshot | None:
        return self._coordinator.data

    @property
    def _forecast(self) -> Forecast | None:
        snapshot = self._snapshot
        if snapshot is None or not snapshot.forecasts:
            return None
        return snapshot.forecasts[0]

    @property
    def available(self) -> bool:
        """A persisted coordinator snapshot, even degraded, is available."""

        return self._snapshot is not None

    @property
    def native_value(self) -> float | None:
        """Return earliest-day P90 distance, never a fabricated zero."""

        forecast = self._forecast
        return None if forecast is None else _kilometres(forecast.distance_p90_m)

    @property
    def extra_state_attributes(self) -> Mapping[str, object]:
        """Return a bounded presentation allowlist without source identifiers."""

        snapshot = self._snapshot
        forecast = self._forecast
        if snapshot is None or forecast is None:
            return {}
        return {
            "service_date": forecast.service_date.isoformat(),
            "distance_p50_km": _kilometres(forecast.distance_p50_m),
            "quality": forecast.quality.value,
            "generated_at": snapshot.generated_at.isoformat(),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one passive distance entity for one profile config entry."""

    del hass
    runtime = cast(ProfileRuntimeData, entry.runtime_data)
    coordinator = runtime.coordinator
    async_add_entities([ForecastDistanceSensor(entry.entry_id, coordinator)])
