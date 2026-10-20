from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mobility_forecast.const import DOMAIN
from custom_components.mobility_forecast.storage import VehicleStore


async def test_recorder_to_sensor_weekend_driver(hass):
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    await hass.config.async_set_time_zone("UTC")
    source = "sensor.odometer"
    start = now - timedelta(weeks=16)
    km = 1000
    states = []
    for i in range(113):
        stamp = start + timedelta(days=i)
        states.append(
            State(source, str(km), {"unit_of_measurement": "km"}, last_updated=stamp)
        )
        if stamp.weekday() >= 5:
            km += 150
    hass.states.async_set(source, states[-1].state, {"unit_of_measurement": "km"})
    entry = MockConfigEntry(
        domain=DOMAIN, title="Weekend car", data={"odometer": source}, unique_id=source
    )
    entry.add_to_hass(hass)

    # Real import code and historical pipeline, replacing only database reads.
    async def executor(job):
        return job()

    from types import SimpleNamespace

    def query(hass, begin, end, *args, **kwargs):
        return {source: [s for s in states if begin <= s.last_updated < end]}

    hass.config.components.add("recorder")
    with (
        patch(
            "homeassistant.components.recorder.get_instance",
            return_value=SimpleNamespace(async_add_executor_job=executor),
        ),
        patch(
            "homeassistant.components.recorder.statistics.get_metadata", return_value={}
        ),
        patch(
            "homeassistant.components.recorder.history.state_changes_during_period",
            return_value={source: states[:1]},
        ),
        patch(
            "homeassistant.components.recorder.history.get_significant_states",
            side_effect=query,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        assert runtime.data.values["next_7_days"] == pytest.approx(300, rel=0.12)
        sensors = [s for s in hass.states.async_all("sensor") if s.entity_id != source]
        assert len(sensors) == 10
        assert all(
            s.state not in ("unknown", "unavailable")
            for s in sensors
            if "last_successful_sync" not in s.entity_id
        )
        assert len(runtime.readings) >= 112
        original = runtime.readings[:]
        assert await hass.config_entries.async_reload(entry.entry_id)
        await entry.runtime_data.import_task
        await hass.async_block_till_done()
        assert entry.runtime_data.readings[0] == original[0]
        await hass.config_entries.async_unload(entry.entry_id)
        assert (await VehicleStore(hass, entry.entry_id).load_readings())[
            0
        ] == original[0]
