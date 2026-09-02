"""Profile-scoped refresh orchestration behind typed read-only boundaries.

This module is independent from Home Assistant. Sources can only read from their
configured adapters, storage is always addressed by config-entry identifier, and
only immutable forecast snapshots are published for later read-only entities.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .domain.models import Forecast
from .storage import ProfileState


def _validate_forecasts(forecasts: tuple[Forecast, ...]) -> None:
    service_dates = tuple(item.service_date for item in forecasts)
    if len(set(service_dates)) != len(service_dates):
        raise ValueError("forecast service dates must be unique")
    if service_dates != tuple(sorted(service_dates)):
        raise ValueError("forecasts must be ordered by service date")


@dataclass(frozen=True, slots=True)
class ProfileUpdate:
    """One source read result, including the next durable profile state."""

    state: ProfileState
    forecasts: tuple[Forecast, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        _validate_forecasts(self.forecasts)


@dataclass(frozen=True, slots=True)
class CoordinatorSnapshot:
    """Immutable, presentation-safe data published after a successful save."""

    forecasts: tuple[Forecast, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        _validate_forecasts(self.forecasts)


class ReadOnlyProfileSource(Protocol):
    """Read configured inputs and run the domain pipeline without actions."""

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        """Return a validated update derived from immutable prior state."""
        ...


class ProfileStorage(Protocol):
    """Persist private state in an explicitly config-entry-scoped namespace."""

    async def load(self, config_entry_id: str) -> ProfileState:
        """Load one entry's state without exposing its raw serialized payload."""
        ...

    async def save(self, config_entry_id: str, state: ProfileState) -> None:
        """Atomically persist one entry's validated immutable state."""
        ...


class ProfileCoordinator:
    """Refresh exactly one profile and publish only completed transactions."""

    def __init__(
        self,
        config_entry_id: str,
        source: ReadOnlyProfileSource,
        storage: ProfileStorage,
    ) -> None:
        if not config_entry_id.strip():
            raise ValueError("config_entry_id must not be empty")
        self._config_entry_id = config_entry_id
        self._source = source
        self._storage = storage
        self._data: CoordinatorSnapshot | None = None
        self._last_update_success = False
        self._listeners: set[Callable[[], None]] = set()

    @property
    def data(self) -> CoordinatorSnapshot | None:
        """Return the last successfully persisted immutable snapshot, if any."""

        return self._data

    @property
    def last_update_success(self) -> bool:
        """Report whether the latest attempted refresh completed successfully."""

        return self._last_update_success

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a presentation callback and return its removal callback."""

        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def refresh(self) -> CoordinatorSnapshot:
        """Read, validate, persist, then atomically publish one profile refresh.

        Exceptions intentionally propagate to the future Home Assistant adapter.
        Publication occurs only after storage succeeds, so failed reads or writes
        leave the previous in-memory snapshot unchanged.
        """

        try:
            previous_state = await self._storage.load(self._config_entry_id)
            update = await self._source.read(previous_state)
            snapshot = CoordinatorSnapshot(update.forecasts, update.generated_at)
            await self._storage.save(self._config_entry_id, update.state)
        except Exception:
            self._last_update_success = False
            self._notify_listeners()
            raise
        self._data = snapshot
        self._last_update_success = True
        self._notify_listeners()
        return snapshot
