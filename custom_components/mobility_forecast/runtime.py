"""Typed composition root for one Home Assistant forecast profile.

Runtime data keeps Home Assistant adapters entry-scoped while exposing only the
specific read-only boundaries each adapter needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .coordinator import ProfileCoordinator, ProfileUpdate
from .diagnostics import DiagnosticsSnapshot
from .storage import ProfileState

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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


class _PendingDiagnosticsSource:
    """Avoid fabricating diagnostics before aggregate source composition exists."""

    async def read(self) -> DiagnosticsSnapshot:
        raise RuntimeError("profile diagnostics source is not configured")


def build_runtime(hass: HomeAssistant, config_entry_id: str) -> ProfileRuntimeData:
    """Build an isolated runtime with durable state and pending read sources.

    Constructing the Home Assistant Store performs no I/O. Source and diagnostics
    remain fail-closed until their own checkpoints, and no refresh or scheduling
    behavior is introduced here.
    """

    from .ha_storage import HomeAssistantProfileStorage

    return ProfileRuntimeData(
        coordinator=ProfileCoordinator(
            config_entry_id,
            source=_PendingProfileSource(),
            storage=HomeAssistantProfileStorage(hass, config_entry_id),
        ),
        diagnostics_source=_PendingDiagnosticsSource(),
    )
