from zoneinfo import ZoneInfo

from custom_components.mobility_forecast.calendar_manager import normalize_events
from custom_components.mobility_forecast.locations import normalize


def test_location_recognition():
    assert normalize("Office") is None
    assert normalize("https://zoom.us/123") is None
    assert normalize("Main Street 10, Amsterdam").source == "address"
    assert normalize("52, 5") == normalize("52.00000,5.00000")
    assert normalize("Office", {"Office": "52,5"}).query == "52.00000,5.00000"
    assert normalize("999,999") is None


def test_events_deduplicate_and_filter():
    event = {
        "start": "2026-03-29T09:00:00+02:00",
        "end": "2026-03-29T10:00:00+02:00",
        "location": "52,5",
    }
    events = normalize_events(
        [
            event,
            event,
            {**event, "status": "cancelled"},
            {**event, "end": event["start"]},
        ],
        ZoneInfo("Europe/Amsterdam"),
    )
    assert len(events) == 1
    assert not events[0].all_day


def test_all_day_and_missing():
    events = normalize_events(
        [{"start": "2026-01-01", "end": "2026-01-02"}], ZoneInfo("UTC")
    )
    assert events[0].all_day
    assert events[0].location is None
