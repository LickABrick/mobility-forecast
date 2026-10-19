"""Behavioral reset evidence, separate from accepted monotonic history."""

from .models import Reading


def reset_count(readings: list[Reading]) -> int:
    """Count decreases on distinct UTC dates, not repeated polls of one glitch."""
    ordered = sorted(readings, key=lambda r: r.timestamp)
    return len(
        {b.timestamp.date() for a, b in zip(ordered, ordered[1:]) if b.km < a.km}
    )
