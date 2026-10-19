from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.waze_travel_time.services import async_setup_services
from pywaze.route_calculator import CalcRoutesResponse

from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import WazeProvider


@pytest.mark.parametrize("region", ["eu", "us", "na", "il", "au"])
async def test_real_waze_service_schema_and_response(hass, region):
    async_setup_services(hass)
    # Real HA service schema, handler, and coordinator conversion. Only the
    # external pywaze client calculation (network boundary) is replaced.
    with patch(
        "pywaze.route_calculator.WazeRouteCalculator.calc_routes",
        new_callable=AsyncMock,
        return_value=[
            CalcRoutesResponse(
                name="route", distance=24.5, duration=18, street_names=[]
            )
        ],
    ) as calculation:
        provider = WazeProvider(hass, region)
        route = await provider.get_route(normalize("52,5"), normalize("53,6"))
        assert route.distance_km == 24.5
        assert route.duration_minutes == 18
        assert calculation.call_args.kwargs["real_time"] is False
        assert calculation.call_args.kwargs["vehicle_type"] == ""
        await provider.get_route(normalize("52,5"), normalize("53,6"))
        assert calculation.await_count == 1


async def test_waze_failure_recovery(hass):
    async_setup_services(hass)
    provider = WazeProvider(hass, "eu")
    with patch(
        "pywaze.route_calculator.WazeRouteCalculator.calc_routes",
        side_effect=TimeoutError,
    ):
        assert await provider.get_route(normalize("52,5"), normalize("53,6")) is None
    with patch(
        "pywaze.route_calculator.WazeRouteCalculator.calc_routes",
        new_callable=AsyncMock,
        return_value=[
            CalcRoutesResponse(name="route", distance=20, duration=15, street_names=[])
        ],
    ):
        assert (
            await provider.get_route(normalize("52,5"), normalize("53,6"))
        ).distance_km == 20
