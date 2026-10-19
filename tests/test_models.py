from datetime import UTC, datetime

from custom_components.mobility_forecast.models import Forecast, Status


def test_unknown_is_not_zero():
    result = Forecast(datetime.now(UTC), Status.LEARNING, {"today": None})
    assert result.values["today"] is None
