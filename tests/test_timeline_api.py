"""Native response actions and opt-in chart entity acceptance."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.models import DailyDistance


async def test_history_response_matches_chart_and_reload(hass):
    entry = MockConfigEntry(
        domain="mobility_forecast", title="Car", data={"odometer": "sensor.car"}
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        "mobility_forecast",
        f"{entry.entry_id}_mileage_timeline",
        config_entry=entry,
        disabled_by=None,
    )
    with patch(
        "custom_components.mobility_forecast.coordinator.import_history",
        return_value=[],
    ):
        assert await async_setup_component(hass, "mobility_forecast", {})
        runtime = entry.runtime_data
        await runtime.initialization_task
        await runtime.import_task
        now = datetime.now(UTC)
        target = now.date() - timedelta(days=1)
        runtime.store.payload["snapshots"][target.isoformat()] = {
            "schema": 1,
            "valid": True,
            "target_date": target.isoformat(),
            "predicted_km": 42,
            "captured_at": datetime.combine(
                target - timedelta(days=1), datetime.min.time(), UTC
            )
            .replace(hour=23, minute=55)
            .isoformat(),
            "calendar_included": True,
        }
        runtime.history_cache = [DailyDistance(target, 48, "observed", 1)]
        await runtime.async_refresh()
        await hass.async_block_till_done()
        result = await hass.services.async_call(
            "mobility_forecast",
            "get_history",
            {"entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
        assert len(result["history"]) == 30
        row = result["history"][-1]
        assert row["date"] == target.isoformat()
        assert row["predicted_km"] == 42 and row["actual_km"] == 48
        assert row["difference_km"] == 6
        state = hass.states.get(entity.entity_id)
        assert state.attributes["history"] == result["history"]
        assert "state_class" not in state.attributes
        future = await hass.services.async_call(
            "mobility_forecast",
            "get_forecast",
            {"entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
        assert future["forecast"] == state.attributes["forecast"]
        assert all("timestamp" in r for r in future["forecast"])
        await hass.config_entries.async_unload(entry.entry_id)
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "mobility_forecast",
                "get_history",
                {"entry_id": entry.entry_id},
                blocking=True,
                return_response=True,
            )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await entry.runtime_data.initialization_task
        await entry.runtime_data.import_task
        assert (
            entry.runtime_data.store.payload["snapshots"][target.isoformat()][
                "predicted_km"
            ]
            == 42
        )
        await hass.config_entries.async_unload(entry.entry_id)
