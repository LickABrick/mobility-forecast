from datetime import UTC, datetime

from custom_components.mobility_forecast.models import Reading
from custom_components.mobility_forecast.storage import VehicleStore


async def test_storage_round_trip(hass):
    store = VehicleStore(hass, "vehicle")
    reading = Reading(datetime(2026, 1, 1, tzinfo=UTC), 100)
    store.schedule([reading])
    await store.flush()
    restored = VehicleStore(hass, "vehicle")
    assert await restored.load_readings() == [reading]
    await restored.async_remove()
    assert await VehicleStore(hass, "vehicle").load_readings() == []
