from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from custom_components.mobility_forecast.coordinator import (
    CoordinatorSnapshot,
    ProfileCoordinator,
    ProfileUpdate,
)
from custom_components.mobility_forecast.domain import DataQuality, Forecast
from custom_components.mobility_forecast.storage import ProfileState

NOW = datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
EMPTY_STATE = ProfileState(revisions=(), pending_days=(), actuals=())


def forecast(service_date: date = date(2026, 1, 16)) -> Forecast:
    return Forecast(
        service_date=service_date,
        distance_p50_m=10_000,
        distance_p90_m=12_000,
        required_soc_p50_percent=None,
        required_soc_p90_percent=None,
        quality=DataQuality.PARTIAL,
        reason_codes=("cold_start",),
    )


class FakeProfileStorage:
    def __init__(self, states: dict[str, ProfileState]) -> None:
        self.states = dict(states)
        self.loads: list[str] = []
        self.saves: list[tuple[str, ProfileState]] = []

    async def load(self, config_entry_id: str) -> ProfileState:
        self.loads.append(config_entry_id)
        return self.states[config_entry_id]

    async def save(self, config_entry_id: str, state: ProfileState) -> None:
        self.saves.append((config_entry_id, state))
        self.states[config_entry_id] = state


class FakeReadOnlySource:
    def __init__(self, updates: list[ProfileUpdate | Exception]) -> None:
        self.updates = list(updates)
        self.previous_states: list[ProfileState] = []

    async def read(self, previous_state: ProfileState) -> ProfileUpdate:
        self.previous_states.append(previous_state)
        result = self.updates.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FailingSaveStorage(FakeProfileStorage):
    async def save(self, config_entry_id: str, state: ProfileState) -> None:
        raise RuntimeError("synthetic save failure")


class ProfileCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_loads_scoped_state_saves_and_publishes_snapshot(
        self,
    ) -> None:
        storage = FakeProfileStorage({"entry-a": EMPTY_STATE})
        update = ProfileUpdate(
            state=EMPTY_STATE,
            forecasts=(forecast(),),
            generated_at=NOW,
        )
        source = FakeReadOnlySource([update])
        coordinator = ProfileCoordinator(
            config_entry_id="entry-a", source=source, storage=storage
        )

        snapshot = await coordinator.refresh()

        self.assertEqual(storage.loads, ["entry-a"])
        self.assertEqual(source.previous_states, [EMPTY_STATE])
        self.assertEqual(storage.saves, [("entry-a", EMPTY_STATE)])
        self.assertEqual(snapshot, CoordinatorSnapshot(update.forecasts, NOW))
        self.assertIs(coordinator.data, snapshot)
        self.assertTrue(coordinator.last_update_success)

    async def test_coordinators_keep_config_entries_isolated(self) -> None:
        state_a = EMPTY_STATE
        state_b = ProfileState(revisions=(), pending_days=(), actuals=())
        storage = FakeProfileStorage({"entry-a": state_a, "entry-b": state_b})
        source_a = FakeReadOnlySource([ProfileUpdate(state_a, (forecast(),), NOW)])
        source_b = FakeReadOnlySource(
            [ProfileUpdate(state_b, (forecast(date(2026, 1, 17)),), NOW)]
        )

        result_a = await ProfileCoordinator("entry-a", source_a, storage).refresh()
        result_b = await ProfileCoordinator("entry-b", source_b, storage).refresh()

        self.assertEqual(storage.loads, ["entry-a", "entry-b"])
        self.assertEqual(
            [entry_id for entry_id, _state in storage.saves], ["entry-a", "entry-b"]
        )
        self.assertNotEqual(
            result_a.forecasts[0].service_date, result_b.forecasts[0].service_date
        )

    async def test_failed_refresh_preserves_last_published_data_and_storage(
        self,
    ) -> None:
        storage = FakeProfileStorage({"entry-a": EMPTY_STATE})
        first = ProfileUpdate(EMPTY_STATE, (forecast(),), NOW)
        source = FakeReadOnlySource([first, RuntimeError("synthetic read failure")])
        coordinator = ProfileCoordinator("entry-a", source, storage)
        published = await coordinator.refresh()

        with self.assertRaisesRegex(RuntimeError, "synthetic read failure"):
            await coordinator.refresh()

        self.assertIs(coordinator.data, published)
        self.assertFalse(coordinator.last_update_success)
        self.assertEqual(len(storage.saves), 1)
        self.assertEqual(storage.loads, ["entry-a", "entry-a"])

    async def test_failed_save_does_not_publish_unpersisted_data(self) -> None:
        storage = FailingSaveStorage({"entry-a": EMPTY_STATE})
        source = FakeReadOnlySource([ProfileUpdate(EMPTY_STATE, (forecast(),), NOW)])
        coordinator = ProfileCoordinator("entry-a", source, storage)

        with self.assertRaisesRegex(RuntimeError, "synthetic save failure"):
            await coordinator.refresh()

        self.assertIsNone(coordinator.data)
        self.assertFalse(coordinator.last_update_success)

    async def test_refresh_notifies_listener_on_success_and_failure(self) -> None:
        storage = FakeProfileStorage({"entry-a": EMPTY_STATE})
        source = FakeReadOnlySource(
            [
                ProfileUpdate(EMPTY_STATE, (forecast(),), NOW),
                RuntimeError("synthetic read failure"),
                ProfileUpdate(EMPTY_STATE, (), NOW),
            ]
        )
        coordinator = ProfileCoordinator("entry-a", source, storage)
        notifications: list[bool] = []
        remove_listener = coordinator.add_listener(
            lambda: notifications.append(coordinator.last_update_success)
        )

        await coordinator.refresh()
        with self.assertRaises(RuntimeError):
            await coordinator.refresh()
        remove_listener()
        await coordinator.refresh()

        self.assertEqual(notifications, [True, False])

    def test_update_rejects_duplicate_or_unordered_forecast_dates(self) -> None:
        duplicate_date = forecast().service_date
        with self.assertRaisesRegex(ValueError, "forecast service dates"):
            ProfileUpdate(
                EMPTY_STATE,
                (forecast(duplicate_date), forecast(duplicate_date)),
                NOW,
            )
        with self.assertRaisesRegex(ValueError, "ordered by service date"):
            ProfileUpdate(
                EMPTY_STATE,
                (forecast(date(2026, 1, 17)), forecast(date(2026, 1, 16))),
                NOW,
            )

    def test_requires_nonempty_entry_id_and_aware_generation_time(self) -> None:
        storage = FakeProfileStorage({"entry-a": EMPTY_STATE})
        source = FakeReadOnlySource([])

        with self.assertRaisesRegex(ValueError, "config_entry_id"):
            ProfileCoordinator(" ", source, storage)
        with self.assertRaisesRegex(ValueError, "generated_at"):
            ProfileUpdate(EMPTY_STATE, (), datetime(2026, 1, 15, 7, 0))


if __name__ == "__main__":
    unittest.main()
