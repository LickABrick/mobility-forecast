"""Deterministic, privacy-preserving calendar-event filtering."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from .models import SourceEvent


class ExclusionReason(StrEnum):
    """Stable aggregate reason codes for events omitted from planning."""

    EXCLUDE_TERM = "exclude_term"
    ONLINE = "online"
    ALL_DAY = "all_day"
    MISSING_LOCATION = "missing_location"
    INCLUDE_MISMATCH = "include_mismatch"


@dataclass(frozen=True, slots=True)
class EventFilterPolicy:
    """Explicit filtering policy owned by one forecast profile.

    Terms are case-insensitive substrings matched only against summary and
    description. Every structural choice is required so this domain contract
    introduces no implicit profile default.
    """

    include_terms: tuple[str, ...]
    exclude_terms: tuple[str, ...]
    allow_online: bool
    allow_all_day: bool
    require_location: bool

    def __post_init__(self) -> None:
        _validate_terms(self.include_terms, "include_terms")
        _validate_terms(self.exclude_terms, "exclude_terms")


@dataclass(frozen=True, slots=True)
class EventFilterDecision:
    """Classification without retaining the source event or its private text."""

    included: bool
    exclusion_reason: ExclusionReason | None

    def __post_init__(self) -> None:
        if self.included == (self.exclusion_reason is not None):
            raise ValueError("included decisions must not have an exclusion reason")


@dataclass(frozen=True, slots=True)
class FilterPreview:
    """Privacy-safe aggregate preview; no source identifiers or text are retained."""

    total_count: int
    included_count: int
    excluded_count: int
    reason_counts: tuple[tuple[ExclusionReason, int], ...]

    def __post_init__(self) -> None:
        if min(self.total_count, self.included_count, self.excluded_count) < 0:
            raise ValueError("preview counts must not be negative")
        if self.included_count + self.excluded_count != self.total_count:
            raise ValueError("included and excluded counts must equal total_count")
        if sum(count for _, count in self.reason_counts) != self.excluded_count:
            raise ValueError("reason counts must equal excluded_count")
        if any(count <= 0 for _, count in self.reason_counts):
            raise ValueError("reason counts must be positive")


def classify_event(
    event: SourceEvent, policy: EventFilterPolicy
) -> EventFilterDecision:
    """Classify one event using documented, stable exclusion precedence."""

    searchable_text = "\n".join(
        value for value in (event.summary, event.description) if value is not None
    ).casefold()

    if _matches_any(searchable_text, policy.exclude_terms):
        reason = ExclusionReason.EXCLUDE_TERM
    elif event.is_online and not policy.allow_online:
        reason = ExclusionReason.ONLINE
    elif event.all_day and not policy.allow_all_day:
        reason = ExclusionReason.ALL_DAY
    elif (
        policy.require_location
        and not event.is_online
        and not (event.location_text and event.location_text.strip())
    ):
        reason = ExclusionReason.MISSING_LOCATION
    elif policy.include_terms and not _matches_any(
        searchable_text, policy.include_terms
    ):
        reason = ExclusionReason.INCLUDE_MISMATCH
    else:
        return EventFilterDecision(included=True, exclusion_reason=None)

    return EventFilterDecision(included=False, exclusion_reason=reason)


def preview_events(
    events: Iterable[SourceEvent], policy: EventFilterPolicy
) -> FilterPreview:
    """Return aggregate counts without retaining event data."""

    total_count = 0
    included_count = 0
    reasons: Counter[ExclusionReason] = Counter()
    for event in events:
        total_count += 1
        decision = classify_event(event, policy)
        if decision.included:
            included_count += 1
        else:
            assert decision.exclusion_reason is not None
            reasons[decision.exclusion_reason] += 1

    reason_counts = tuple(
        (reason, reasons[reason]) for reason in ExclusionReason if reasons[reason]
    )
    return FilterPreview(
        total_count=total_count,
        included_count=included_count,
        excluded_count=total_count - included_count,
        reason_counts=reason_counts,
    )


def _validate_terms(terms: tuple[str, ...], field_name: str) -> None:
    normalized = tuple(term.strip().casefold() for term in terms)
    if any(not term for term in normalized):
        raise ValueError(f"{field_name} must not contain empty terms")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate terms")


def _matches_any(searchable_text: str, terms: tuple[str, ...]) -> bool:
    return any(term.strip().casefold() in searchable_text for term in terms)
