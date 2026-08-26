"""Typed composition root for one Home Assistant forecast profile.

Runtime data keeps Home Assistant adapters entry-scoped while exposing only the
specific read-only boundaries each adapter needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .coordinator import ProfileCoordinator
from .diagnostics import DiagnosticsSnapshot


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
