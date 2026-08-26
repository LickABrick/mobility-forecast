"""Typed composition root for one Home Assistant forecast profile.

Runtime data keeps Home Assistant adapters entry-scoped while exposing only the
specific read-only boundaries each adapter needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .coordinator import ProfileCoordinator, ProfileUpdate
from .diagnostics import DiagnosticsSnapshot
from .storage import ProfileState


class DiagnosticsSource(Protocol):
    """Build one current aggregate snapshot without exposing private raw state."""

    async def read(self) -> DiagnosticsSnapshot:
        """Return the versioned diagnostics input for this profile."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileRuntimeData:
    """Entry-scoped read-only boundaries shared by Home Assistant adapters."""

    coordinator: ProfileCoordinator
    diagnostics_source: DiagnosticsSource


class _PendingProfileSource:
    """Fail closed until the separately reviewed source adapter is composed."""

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        del previous_state
        raise RuntimeError("profile source adapter is not configured")


class _PendingProfileStorage:
    """Fail closed until the Home Assistant Store checkpoint is complete."""

    async def load(self, config_entry_id: str) -> ProfileState:
        del config_entry_id
        raise RuntimeError("profile storage adapter is not configured")

    async def save(self, config_entry_id: str, state: ProfileState) -> None:
        del config_entry_id, state
        raise RuntimeError("profile storage adapter is not configured")


class _PendingDiagnosticsSource:
    """Avoid fabricating diagnostics before aggregate source composition exists."""

    async def read(self) -> DiagnosticsSnapshot:
        raise RuntimeError("profile diagnostics source is not configured")


def build_pending_runtime(config_entry_id: str) -> ProfileRuntimeData:
    """Build an isolated fail-closed runtime for the lifecycle-only checkpoint.

    Platform setup can safely expose an unavailable passive sensor now. Later
    adapter checkpoints replace these boundaries; this factory performs no I/O
    and establishes no source, storage, refresh, or scheduling default.
    """

    return ProfileRuntimeData(
        coordinator=ProfileCoordinator(
            config_entry_id,
            source=_PendingProfileSource(),
            storage=_PendingProfileStorage(),
        ),
        diagnostics_source=_PendingDiagnosticsSource(),
    )
