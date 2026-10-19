"""Opt-in bounded-memory compaction benchmark (not part of regular CI)."""

import tracemalloc
from datetime import UTC, datetime, timedelta
from time import perf_counter

from custom_components.mobility_forecast.history import compact_readings
from custom_components.mobility_forecast.models import Reading


def run():
    start = datetime(2023, 1, 1, tzinfo=UTC)
    print("frequency_seconds,input_count,retained_count,seconds,peak_python_mib")
    for frequency in (10, 60, 3600, 86400 * 3):
        # Generator is deliberate: measure compactor, not an allocated raw list.
        count = 1095 * 86400 // frequency + 1
        tracemalloc.start()
        began = perf_counter()
        retained = compact_readings(
            Reading(
                start + timedelta(seconds=i * frequency),
                100 + i * frequency / 86400 * 40,
            )
            for i in range(count)
        )
        elapsed = perf_counter() - began
        peak = tracemalloc.get_traced_memory()[1] / 1024**2
        tracemalloc.stop()
        print(f"{frequency},{count},{len(retained)},{elapsed:.3f},{peak:.2f}")


if __name__ == "__main__":
    run()
