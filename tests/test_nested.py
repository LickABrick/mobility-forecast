from datetime import UTC, datetime, timedelta
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.mobility_forecast.calendar_manager import (
    Appointment,
    preprocess_appointments,
)
from custom_components.mobility_forecast.locations import normalize
from custom_components.mobility_forecast.routing import Route, plan_journeys


def event(start, end, loc="52,5", identifier=None, all_day=False):
    base = datetime(2026, 3, 29, tzinfo=ZoneInfo("Europe/Amsterdam"))
    return Appointment(
        base + timedelta(hours=start),
        base + timedelta(hours=end),
        normalize(loc),
        all_day,
        identifier or str((start, end, loc)),
    )


async def test_nested_chain_and_order():
    events = [
        event(8, 12),
        event(9, 9.75, "53,6"),
        event(10, 10.5, "54,7"),
        event(10, 10.25, None),
    ]
    for order in permutations(events):
        selected, ignored = preprocess_appointments(order, True)
        assert selected == [events[0]] and ignored == 3
    provider = SimpleNamespace(get_route=AsyncMock(return_value=Route(10, 0)))
    plans = await plan_journeys(selected, normalize("51,4"), provider)
    assert next(iter(plans.values())).distance_km == 20
    assert provider.get_route.await_count == 2
    strict, _ = preprocess_appointments(events, False)
    assert not next(
        iter((await plan_journeys(strict, normalize("51,4"), provider)).values())
    ).complete


@pytest.mark.parametrize(
    "events,ignored",
    [
        ([event(8, 17), event(9, 13, "53,6"), event(10, 11, "54,7")], 2),
        ([event(9, 10), event(9, 10, "53,6")], 0),
        ([event(8, 12), event(11, 13, "53,6")], 0),
        ([event(8, 12, None), event(9, 10)], 0),
        ([event(0, 24, all_day=True), event(9, 10)], 0),
        ([event(8, 10), event(10, 11, "53,6")], 0),
        ([event(20, 30), event(21, 22, "53,6")], 0),
    ],
)
def test_containment_edges(events, ignored):
    for order in permutations(events):
        assert preprocess_appointments(order, True)[1] == ignored


def test_instants_and_virtual():
    parent = event(8, 12)
    child = Appointment(
        parent.start.astimezone(UTC) + timedelta(hours=1),
        parent.end.astimezone(UTC) - timedelta(hours=1),
        None,
        False,
        "child",
    )
    virtual = Appointment(parent.start, parent.end, None, False, "virtual", True)
    assert preprocess_appointments([child, virtual, parent], True) == ([parent], 1)
