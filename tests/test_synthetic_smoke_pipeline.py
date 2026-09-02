from __future__ import annotations

import importlib
import sys
import types
import unittest
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from custom_components.mobility_forecast.coordinator import ProfileCoordinator
from custom_components.mobility_forecast.domain import (
    Coordinates,
    DataQuality,
    DeterministicRouteProvider,
    EventFilterPolicy,
    ForecastPolicy,
    LocationProvenance,
    ResolvedLocation,
    Route,
    RouteFailure,
    RouteFailureCategory,
    RouteOptions,
    RouteRequest,
    RouteSuccess,
)
from custom_components.mobility_forecast.ha_calendar import (
    CalendarSourceConfig,
    HomeAssistantCalendarSource,
)
from custom_components.mobility_forecast.storage import ProfileState
from tests.synthetic_pipeline import (
    SyntheticCalendarComponent,
    SyntheticCalendarEntity,
    SyntheticCalendarEvent,
    SyntheticPipelineProfileSource,
    SyntheticProfileStorage,
)

NOW = datetime(2032, 4, 5, 7, 0, tzinfo=UTC)
STARTS_AT = NOW + timedelta(hours=2)
ENDS_AT = STARTS_AT + timedelta(hours=1)
WINDOW_END = NOW + timedelta(days=1)
ENTRY_ID = "entry-synthetic-smoke"
OPTIONS = RouteOptions(avoid_tolls=False, avoid_highways=False)
EMPTY_STATE = ProfileState(revisions=(), pending_days=(), actuals=())
SENSOR_MODULE = "custom_components.mobility_forecast.sensor"


class FakeSensorEntity:
    pass


class FakeUnitOfLength:
    KILOMETERS = "km"


@contextmanager
def fake_home_assistant_sensor() -> Generator[None]:
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    sensor = types.ModuleType("homeassistant.components.sensor")
    sensor.SensorEntity = FakeSensorEntity  # type: ignore[attr-defined]
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object  # type: ignore[attr-defined]
    const = types.ModuleType("homeassistant.const")
    const.UnitOfLength = FakeUnitOfLength  # type: ignore[attr-defined]
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object  # type: ignore[attr-defined]
    helpers = types.ModuleType("homeassistant.helpers")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddConfigEntryEntitiesCallback = (  # type: ignore[attr-defined]
        Callable[[list[object]], None]
    )
    modules = {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.sensor": sensor,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.entity_platform": entity_platform,
    }
    previous = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        sys.modules.pop(SENSOR_MODULE, None)
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def location(
    endpoint_id: str,
    latitude: float,
    longitude: float,
    provenance: LocationProvenance,
) -> ResolvedLocation:
    return ResolvedLocation(
        endpoint_id=endpoint_id,
        coordinates=Coordinates(latitude, longitude),
        provenance=provenance,
        observed_at=NOW,
        quality=DataQuality.COMPLETE,
    )


def calendar_source() -> HomeAssistantCalendarSource:
    entity = SyntheticCalendarEntity(
        [
            SyntheticCalendarEvent(
                start=STARTS_AT,
                end=ENDS_AT,
                summary="Synthetic included appointment",
                description="Fixture content only",
                location="Synthetic destination alpha",
                uid="synthetic-included",
            ),
            SyntheticCalendarEvent(
                start=STARTS_AT + timedelta(hours=2),
                end=ENDS_AT + timedelta(hours=2),
                summary="Synthetic excluded online appointment",
                location="synthetic-video://room",
                uid="synthetic-online",
            ),
        ]
    )
    return HomeAssistantCalendarSource(
        hass=object(),
        component=SyntheticCalendarComponent({"calendar.synthetic": entity}),
        config=CalendarSourceConfig(("calendar.synthetic",)),
        classify_online=lambda event: event.location == "synthetic-video://room",
    )


def pipeline_source(
    provider: DeterministicRouteProvider,
    origin: ResolvedLocation,
    destination: ResolvedLocation,
) -> SyntheticPipelineProfileSource:
    return SyntheticPipelineProfileSource(
        calendar_source=calendar_source(),
        window_start=NOW,
        window_end=WINDOW_END,
        generated_at=NOW,
        revision_id="synthetic-revision-1",
        filter_policy=EventFilterPolicy(
            include_terms=(),
            exclude_terms=(),
            allow_physical=True,
            allow_online=False,
            allow_all_day=False,
            require_location=True,
        ),
        initial_origin=origin,
        destinations={"Synthetic destination alpha": destination},
        route_options=OPTIONS,
        route_provider=provider,
        forecast_policy=ForecastPolicy(
            minimum_history_samples=3,
            minimum_correction_ratio=0.5,
            maximum_correction_ratio=2.0,
            cold_start_p90_multiplier=1.25,
        ),
    )


class SyntheticSmokePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_calendar_to_fake_route_to_sensor_projects_cold_start_distance(
        self,
    ) -> None:
        origin = location("synthetic-origin", 10.0, 20.0, LocationProvenance.ZONE)
        destination = location(
            "synthetic-destination", 11.0, 21.0, LocationProvenance.EVENT
        )
        request = RouteRequest(origin, destination, OPTIONS, STARTS_AT)
        provider = DeterministicRouteProvider(
            "synthetic-fake:v1",
            {
                request: RouteSuccess(
                    Route(
                        origin=origin,
                        destination=destination,
                        distance_m=10_000,
                        duration_s=900,
                        provider="synthetic-fake",
                        observed_at=NOW,
                        quality=DataQuality.COMPLETE,
                    )
                )
            },
        )
        storage = SyntheticProfileStorage({ENTRY_ID: EMPTY_STATE})
        coordinator = ProfileCoordinator(
            ENTRY_ID, pipeline_source(provider, origin, destination), storage
        )

        snapshot = await coordinator.refresh()

        with fake_home_assistant_sensor():
            sensor_module = importlib.import_module(SENSOR_MODULE)
            entity = sensor_module.ForecastDistanceSensor(ENTRY_ID, coordinator)

        self.assertEqual(provider.requests, (request,))
        self.assertEqual(len(storage.states[ENTRY_ID].revisions), 1)
        self.assertEqual(snapshot.forecasts[0].quality, DataQuality.PARTIAL)
        self.assertEqual(entity.native_value, 12.5)
        self.assertEqual(
            entity.extra_state_attributes,
            {
                "service_date": "2032-04-05",
                "distance_p50_km": 10.0,
                "quality": "partial",
                "generated_at": NOW.isoformat(),
            },
        )
        projected = repr(entity.extra_state_attributes)
        self.assertNotIn("Synthetic included appointment", projected)
        self.assertNotIn("Synthetic destination alpha", projected)
        self.assertNotIn(ENTRY_ID, projected)

    async def test_fake_route_failure_stays_unknown_in_sensor_not_zero(self) -> None:
        origin = location("synthetic-origin", 10.0, 20.0, LocationProvenance.ZONE)
        destination = location(
            "synthetic-destination", 11.0, 21.0, LocationProvenance.EVENT
        )
        request = RouteRequest(origin, destination, OPTIONS, STARTS_AT)
        provider = DeterministicRouteProvider(
            "synthetic-fake:v1",
            {
                request: RouteFailure(
                    RouteFailureCategory.TRANSIENT, "synthetic-fake", NOW
                )
            },
        )
        storage = SyntheticProfileStorage({ENTRY_ID: EMPTY_STATE})
        coordinator = ProfileCoordinator(
            ENTRY_ID, pipeline_source(provider, origin, destination), storage
        )

        snapshot = await coordinator.refresh()

        with fake_home_assistant_sensor():
            sensor_module = importlib.import_module(SENSOR_MODULE)
            entity = sensor_module.ForecastDistanceSensor(ENTRY_ID, coordinator)

        revision = storage.states[ENTRY_ID].revisions[0]
        self.assertEqual(revision.quality, DataQuality.PARTIAL)
        self.assertEqual(revision.legs[0].reason_codes, ("route_transient",))
        self.assertEqual(snapshot.forecasts[0].quality, DataQuality.UNAVAILABLE)
        self.assertTrue(entity.available)
        self.assertIsNone(entity.native_value)
        self.assertIsNone(entity.extra_state_attributes["distance_p50_km"])
        self.assertEqual(entity.extra_state_attributes["quality"], "unavailable")


if __name__ == "__main__":
    unittest.main()
