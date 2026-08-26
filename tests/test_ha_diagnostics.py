from __future__ import annotations

import asyncio
import json
import unittest
from datetime import UTC, datetime

from custom_components.mobility_forecast.diagnostics import (
    DiagnosticsSnapshot,
    async_get_config_entry_diagnostics,
    diagnostics_payload,
)
from custom_components.mobility_forecast.domain import DataQuality
from custom_components.mobility_forecast.domain.calendar_filters import (
    ExclusionReason,
    FilterPreview,
)
from custom_components.mobility_forecast.runtime import ProfileRuntimeData

NOW = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def snapshot() -> DiagnosticsSnapshot:
    return DiagnosticsSnapshot(
        generated_at=NOW,
        quality=DataQuality.PARTIAL,
        filter_preview=FilterPreview(3, 2, 1, ((ExclusionReason.MISSING_LOCATION, 1),)),
        planned_leg_count=2,
        degraded_leg_count=1,
        plan_revision_count=4,
        training_actual_count=3,
        route_cache_entry_count=2,
        route_failure_counts=(),
    )


class FakeDiagnosticsSource:
    def __init__(self, result: DiagnosticsSnapshot | Exception) -> None:
        self.result = result
        self.read_count = 0

    async def read(self) -> DiagnosticsSnapshot:
        self.read_count += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeConfigEntry:
    def __init__(self, runtime_data: object) -> None:
        self.entry_id = "private-entry-id"
        self.title = "Private profile title"
        self.data = {"token": "private-credential"}
        self.options = {"latitude": 52.0, "address": "Private address"}
        self.runtime_data = runtime_data


class HomeAssistantDiagnosticsAdapterTests(unittest.TestCase):
    def test_adapter_uses_only_typed_runtime_projection(self) -> None:
        expected_snapshot = snapshot()
        source = FakeDiagnosticsSource(expected_snapshot)
        runtime = ProfileRuntimeData(
            coordinator=object(),  # type: ignore[arg-type]
            diagnostics_source=source,
        )
        entry = FakeConfigEntry(runtime)

        payload = asyncio.run(async_get_config_entry_diagnostics(object(), entry))

        self.assertEqual(payload, diagnostics_payload(expected_snapshot))
        self.assertEqual(source.read_count, 1)
        rendered = json.dumps(payload)
        for private_value in (
            entry.entry_id,
            entry.title,
            "private-credential",
            "Private address",
            "52.0",
        ):
            self.assertNotIn(private_value, rendered)

    def test_source_failure_propagates_without_dumping_entry_data(self) -> None:
        source = FakeDiagnosticsSource(RuntimeError("synthetic diagnostics failure"))
        runtime = ProfileRuntimeData(
            coordinator=object(),  # type: ignore[arg-type]
            diagnostics_source=source,
        )
        entry = FakeConfigEntry(runtime)

        with self.assertRaisesRegex(RuntimeError, "synthetic diagnostics failure"):
            asyncio.run(async_get_config_entry_diagnostics(object(), entry))

        self.assertEqual(source.read_count, 1)


if __name__ == "__main__":
    unittest.main()
