"""Large-calendar discovery remains bounded without mileage provider calls."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.mobility_forecast.ev.coordinator import EVRuntime
from custom_components.mobility_forecast.ev.models import JourneyLeg, Stop
from custom_components.mobility_forecast.models import DailyForecast, Forecast, Status
from custom_components.mobility_forecast.routing import Plan


@pytest.mark.parametrize("count", [30, 150, 300])
async def test_destination_batch_bound(hass, count):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    now = datetime.now(UTC)
    tomorrow = now + timedelta(days=1)
    entry = MockConfigEntry(
        domain="mobility_forecast",
        data={"odometer": "sensor.car"},
        options={
            "ev_enabled": True,
            "soc_entity": "sensor.soc",
            "usable_capacity_kwh": 60,
            "consumption_kwh_per_100km": 20,
            "max_ac_charge_power_kw": 11,
            "charging_mode": "appointments_only",
            "external_lookup_consent": True,
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.soc", "40", {"unit_of_measurement": "%"})
    stops = tuple(
        Stop(tomorrow, tomorrow + timedelta(hours=2), str(i), "PRIVATE")
        for i in range(count)
    )
    leg = JourneyLeg(tomorrow - timedelta(hours=1), tomorrow, 10, 60, "home", "office")
    parent = SimpleNamespace(
        hass=hass,
        entry=entry,
        store=SimpleNamespace(payload={}, schedule_routes=lambda: None),
        plans={tomorrow.date(): Plan(10, True, legs=(leg,), stops=stops)},
        readings=[],
        data=Forecast(
            now,
            Status.READY,
            {},
            days=[DailyForecast(tomorrow.date(), 10, 10, 8, 12)],
            quality="good",
        ),
    )
    runtime = EVRuntime(parent)
    with (
        patch(
            "custom_components.mobility_forecast.ev.coordinator.resolve",
            return_value=((52, 5), "resolved"),
        ) as geo,
        patch(
            "custom_components.mobility_forecast.ev.coordinator.discover",
            return_value=[],
        ) as points,
    ):
        await runtime.update()
        assert geo.call_count == 10
        assert points.call_count == 10
        await runtime.update()
        assert geo.call_count == 10  # SoC/unchanged forecast does not refetch.
        assert len(runtime.result["opportunities"]) == 0
    await runtime.close()
