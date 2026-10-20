"""Validated intervals, conservative daily allocation and bounded recorder import."""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta
from functools import partial
from zoneinfo import ZoneInfo

from .const import HISTORY_DAYS
from .models import DailyDistance, Reading
from .odometer import InvalidReading, kilometers

_LOGGER = logging.getLogger(__name__)
MAX_SPEED_KMH = 240


class ResettingCounterError(ValueError):
    """Raw history contains repeated counter resets."""


def merge_readings(
    existing: list[Reading], incoming: list[Reading]
) -> tuple[list[Reading], int]:
    """Prefer raw/live samples; never let a late sample introduce a negative interval."""
    priority = {"statistics": 0, "recorder": 1, "live": 2}
    indexed = {}
    # Previously accepted samples are anchors: late glitches must not evict
    # trustworthy subsequent readings merely by sorting before them.
    from bisect import bisect_right

    trusted = sorted(
        (r for r in existing if r.source != "statistics"), key=lambda r: r.timestamp
    )
    stamps = [r.timestamp for r in trusted]
    safe_incoming = []
    pre_rejected = 0
    for item in incoming:
        position = (
            bisect_right(stamps, item.timestamp)
            if item.timestamp.tzinfo
            else len(trusted)
        )
        after = trusted[position] if position < len(trusted) else None
        if after is not None and item.km > after.km:
            pre_rejected += 1
        else:
            safe_incoming.append(item)
    combined = existing + safe_incoming
    raw = [
        r.timestamp
        for r in combined
        if r.source != "statistics" and r.timestamp.tzinfo is not None
    ]
    raw = sorted(set(raw))
    from bisect import bisect_left

    def raw_covers(stamp):
        position = bisect_left(raw, stamp)
        if position < len(raw) and raw[position] == stamp:
            return True
        # Only a short raw bracket supersedes hourly statistics. A multi-hour
        # gap is not evidence that raw data covers its interior.
        return 0 < position < len(raw) and raw[position] - raw[
            position - 1
        ] <= timedelta(hours=2)

    for item in sorted(combined, key=lambda r: priority.get(r.source, 0)):
        # Raw telemetry has better time resolution than hourly statistics. Do not
        # interleave stale hourly states into a raw interval or count both sources.
        if item.source == "statistics" and raw_covers(item.timestamp):
            continue
        indexed[item.timestamp] = item
    accepted: list[Reading] = []
    rejected = pre_rejected
    for item in sorted(indexed.values(), key=lambda r: r.timestamp):
        if item.timestamp.tzinfo is None:
            rejected += 1
            continue
        try:
            kilometers(item.km, "km")
        except InvalidReading:
            rejected += 1
            continue
        if accepted:
            previous = accepted[-1]
            hours = (
                item.timestamp.astimezone(UTC) - previous.timestamp.astimezone(UTC)
            ).total_seconds() / 3600
            delta = item.km - previous.km
            if delta < 0 or delta > max(2, hours * MAX_SPEED_KMH):
                rejected += 1
                continue
        accepted.append(item)
    if accepted:
        cutoff = accepted[-1].timestamp - timedelta(days=HISTORY_DAYS)
        accepted = compact_readings([r for r in accepted if r.timestamp >= cutoff])
    return accepted, rejected


def compact_readings(readings: Iterable[Reading]) -> list[Reading]:
    """Keep boundary evidence and cumulative totals, not every telemetry report.

    First/last samples per UTC hour preserve local midnight evidence (including
    fractional-offset zones within the hour). Identical values are still fresh
    observations. No synthetic samples or exact daily values are invented.
    At most 48 samples/day (~52,600 for three years), independent of report rate.
    """
    result: list[Reading] = []
    first = last = None
    bucket = None
    for reading in readings:
        hour = int(reading.timestamp.timestamp()) // 3600
        if hour != bucket:
            if first is not None:
                result.append(first)
                if last is not None and last != first:
                    result.append(last)
            first = reading
            bucket = hour
        last = reading
    if first is not None:
        result.append(first)
        if last is not None and last != first:
            result.append(last)
    return result


def daily_distances(readings: list[Reading], zone: ZoneInfo) -> list[DailyDistance]:
    """Allocate intervals by elapsed time, explicitly estimated except midnight boundaries.

    Coverage describes fresh measurement brackets, not accuracy of intra-interval allocation.
    Days without any bracket remain unknown. Intervals over 14 days are not useful samples.
    """
    buckets: dict = {}
    for left, right in zip(readings, readings[1:]):
        seconds = (
            right.timestamp.astimezone(UTC) - left.timestamp.astimezone(UTC)
        ).total_seconds()
        if seconds <= 0 or seconds > 14 * 86400:
            continue
        start, end = left.timestamp.astimezone(zone), right.timestamp.astimezone(zone)
        day = start.date()
        while day <= end.date():
            midnight = datetime.combine(day, time(), zone)
            following = datetime.combine(day + timedelta(days=1), time(), zone)
            a = max(left.timestamp.astimezone(UTC), midnight.astimezone(UTC))
            b = min(right.timestamp.astimezone(UTC), following.astimezone(UTC))
            duration = (b - a).total_seconds()
            if duration > 0:
                distance = (right.km - left.km) * duration / seconds
                bucket = buckets.setdefault(day, [0.0, 0.0, True, 0.0])
                bucket[0] += distance
                bucket[1] += (
                    duration
                    / (
                        following.astimezone(UTC) - midnight.astimezone(UTC)
                    ).total_seconds()
                )
                # Only exact boundary readings or wholly contained intervals support precise totals.
                exact = (
                    start >= midnight
                    and end <= following
                    and left.source != "statistics"
                    and right.source != "statistics"
                )
                bucket[2] = bucket[2] and exact
                if exact:
                    bucket[3] += right.km - left.km
            day += timedelta(days=1)
    if not readings:
        return []
    # Consistent end-of-day reports provide weaker date attribution: the delta
    # usually belongs to the report day, not a uniform midnight split. Require
    # repeated near-daily cadence, evening timestamps and physical raw states.
    cadence = {}
    candidates = []
    for left, right in zip(readings, readings[1:]):
        a, b = left.timestamp.astimezone(zone), right.timestamp.astimezone(zone)
        hours = (
            right.timestamp.astimezone(UTC) - left.timestamp.astimezone(UTC)
        ).total_seconds() / 3600
        if (
            20 <= hours <= 28
            and b.date() == a.date() + timedelta(days=1)
            and 16 <= a.hour <= 23
            and 16 <= b.hour <= 23
            and abs(a.hour - b.hour) <= 1
            and left.source != "statistics"
            and right.source != "statistics"
        ):
            candidates.append((b.date(), right.km - left.km))
    if len(candidates) >= 14:
        cadence = dict(candidates)
    result = []
    day = readings[0].timestamp.astimezone(zone).date()
    last = readings[-1].timestamp.astimezone(zone).date()
    while day <= last:
        if day in buckets:
            km, coverage, exact, minimum = buckets[day]
            quality = (
                "observed"
                if exact and coverage >= 0.99
                else "estimated"
                if coverage >= 0.9
                else "partial"
            )
            result.append(
                DailyDistance(
                    day,
                    km,
                    quality,
                    min(coverage, 1),
                    minimum,
                    cadence.get(day),
                    0.5 if day in cadence else 0.0,
                )
            )
        else:
            result.append(DailyDistance(day, None, "unknown"))
        day += timedelta(days=1)
    return result


async def import_history(
    hass, entity_id: str, now: datetime, since: datetime | None = None
) -> list[Reading]:
    """Use recorder's own executor. Fetch state statistics, never cumulative sum."""
    if "recorder" not in hass.config.components:
        return []
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.history import (
        get_significant_states,
        state_changes_during_period,
    )
    from homeassistant.components.recorder.statistics import (
        get_metadata,
        statistics_during_period,
    )

    recorder = get_instance(hass)
    start = since or now - timedelta(days=HISTORY_DAYS)
    imported = []
    reset_dates = set()
    previous_raw = None
    try:
        metadata = await recorder.async_add_executor_job(
            partial(get_metadata, hass, statistic_ids={entity_id})
        )
        meta = metadata.get(entity_id)
        if (
            meta
            and meta[1].get("unit_of_measurement") in ("km", "mi")
            and meta[1].get("has_sum")
        ):
            unit = meta[1]["unit_of_measurement"]
            cursor = start
            while cursor < now:
                end = min(now, cursor + timedelta(days=90))
                rows = await recorder.async_add_executor_job(
                    partial(
                        statistics_during_period,
                        hass,
                        cursor,
                        end,
                        {entity_id},
                        "hour",
                        None,
                        {"state"},
                    )
                )
                for row in rows.get(entity_id, []):
                    if row.get("state") is not None:
                        try:
                            # state is the final physical state of the statistics hour.
                            stamp = datetime.fromtimestamp(
                                row["start"], UTC
                            ) + timedelta(hours=1)
                            if stamp <= now:
                                imported.append(
                                    Reading(
                                        stamp,
                                        kilometers(row["state"], unit),
                                        "statistics",
                                        entity_id,
                                    )
                                )
                        except InvalidReading, ValueError, TypeError:
                            continue
                imported, _ = await hass.async_add_executor_job(
                    merge_readings, imported, []
                )
                cursor = end
        # Supported history API: one ascending, row-limited query finds the
        # first retained change for this entity without guessing purge settings.
        earliest = await recorder.async_add_executor_job(
            partial(
                state_changes_during_period,
                hass,
                start,
                now,
                entity_id,
                limit=1,
                include_start_time_state=False,
            )
        )
        retained = earliest.get(entity_id, [])
        cursor = max(start, retained[0].last_updated) if retained else now
        # History windows exclude their lower bound. Preserve the boundary
        # observation itself rather than losing the first retained anchor.
        if retained:
            first = retained[0]
            try:
                anchor = Reading(
                    first.last_updated,
                    kilometers(
                        first.state, first.attributes.get("unit_of_measurement")
                    ),
                    "recorder",
                    entity_id,
                )
                imported, _ = await hass.async_add_executor_job(
                    merge_readings, imported, [anchor]
                )
                previous_raw = anchor
            except InvalidReading:
                pass
        while cursor < now:
            # Six-hour raw batches bound the materialized recorder response even
            # for a 10-second source (2160 states/batch rather than 259200).
            end = min(now, cursor + timedelta(hours=6))
            states = await recorder.async_add_executor_job(
                partial(
                    get_significant_states,
                    hass,
                    cursor,
                    end,
                    [entity_id],
                    include_start_time_state=False,
                    significant_changes_only=False,
                )
            )
            batch = []
            for state in states.get(entity_id, []):
                if isinstance(state, dict):
                    continue
                try:
                    batch.append(
                        Reading(
                            state.last_updated,
                            kilometers(
                                state.state, state.attributes.get("unit_of_measurement")
                            ),
                            "recorder",
                            entity_id,
                        )
                    )
                except InvalidReading:
                    continue
            for reading in sorted(batch, key=lambda r: r.timestamp):
                if (
                    previous_raw
                    and reading.timestamp > previous_raw.timestamp
                    and reading.km < previous_raw.km
                ):
                    reset_dates.add(reading.timestamp.date())
                previous_raw = reading
            if len(reset_dates) >= 2:
                raise ResettingCounterError
            imported, _ = await hass.async_add_executor_job(
                merge_readings, imported, batch
            )
            cursor = end
    except ResettingCounterError:
        raise
    except Exception:  # recorder unavailability must not prevent local forecasting
        _LOGGER.warning(
            "Historical import could not complete; retained existing vehicle data"
        )
    return imported
