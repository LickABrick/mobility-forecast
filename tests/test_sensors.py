from datetime import UTC, datetime
from types import SimpleNamespace

from custom_components.mobility_forecast.models import Forecast, Status
from custom_components.mobility_forecast.sensor import ForecastSensor


def test_sensor_unknown_and_metadata():
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="vehicle", title="Car"),
        data=Forecast(datetime.now(UTC), Status.LEARNING, {"today": None}),
        calendar_status="disabled",
        calendar_metrics={},
    )
    entity = ForecastSensor(coordinator, "today")
    assert entity.native_value is None
    assert entity.unique_id == "vehicle_today"
    assert entity.native_unit_of_measurement == "km"
    assert entity.extra_state_attributes["forecast_status"] == "learning"
