from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import WazeProvider


@pytest.mark.parametrize(
    "left,right",
    [
        (" Main   Street 10,Arnhem ", "MAIN STREET 10 , ARNHEM"),
        ("52, 5", "52.00000,5.00000"),
        ("52.0,5.0", "52,5"),
        ("-0,5", "0.000,5"),
    ],
)
def test_safe_equivalence(left, right):
    assert normalize(left) == normalize(right)


@pytest.mark.parametrize(
    "left,right",
    [
        ("Main Street 10, Arnhem", "Main Street 11, Arnhem"),
        ("Main Street 10, Arnhem", "Main Street 10, 6811 AB Arnhem"),
        ("52.000001,5", "52.000002,5"),
        ("Main Street 10A, Arnhem", "Main Street 10B, Arnhem"),
    ],
)
def test_no_fuzzy_merging(left, right):
    assert normalize(left) != normalize(right)


async def test_alias_queries_and_direction_region_separation():
    services = SimpleNamespace(
        has_service=Mock(return_value=True),
        async_call=AsyncMock(
            return_value={"routes": [{"distance": 12, "duration": 1}]}
        ),
    )
    hass = SimpleNamespace(services=services)
    cache = {}
    a = normalize("51,4")
    alias = normalize(" office ", {" Office ": "Main Street 10, Arnhem"})
    direct = normalize("MAIN STREET 10 , ARNHEM")
    assert alias == direct
    provider = WazeProvider(hass, "eu", cache)
    await provider.get_route(a, alias)
    await provider.get_route(a, direct)
    assert services.async_call.await_count == 1
    assert (
        services.async_call.call_args.args[2]["destination"] == "Main Street 10, Arnhem"
    )
    await provider.get_route(direct, a)
    await WazeProvider(hass, "us", cache).get_route(a, direct)
    assert services.async_call.await_count == 3
    changed = normalize("Office", {"Office": "Other Street 20, Arnhem"})
    await provider.get_route(a, changed)
    assert services.async_call.await_count == 4
