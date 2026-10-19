# API verification

The available package index returned Home Assistant **2026.2.3** as newest; the requested 2026.10.3 GitHub source returned HTTP 404. Minimum and primary locally tested target is therefore 2026.2.3, Python 3.13.2+. Compatibility with 2026.10 is not claimed without testing.

Verified against installed `homeassistant` source (2026.2.3):

- `components/recorder/history/__init__.py`: `get_significant_states(hass, start_time, end_time=None, entity_ids=None, filters=None, include_start_time_state=True, significant_changes_only=True, minimal_response=False, no_attributes=False, compressed_state_format=False)`. Execute via recorder `get_instance(hass).async_add_executor_job`.
- `components/recorder/statistics.py`: `statistics_during_period(hass,start_time,end_time,statistic_ids,period,units,types)`. Import `state`, never treat `sum` as physical odometer. Metadata includes unit and supported statistics.
- `components/calendar/__init__.py`: response-only `calendar.get_events`, start_date_time/end_date_time, target entity IDs, response keyed by entity ID with events. Entity state is not a future event list.
- `components/waze_travel_time/__init__.py`: response-only `get_travel_times`, origin/destination/region/realtime/vehicle_type/units; returns `{'routes': [vars(route), ...]}`. `hass.services.async_call(..., blocking=True, return_response=True)` retrieves response.
- Config entries support typed `runtime_data`, platform forwarding, unload callbacks, reconfigure and options flows.
- Storage `Store` provides atomic writes and `async_delay_save`, `async_save`, `async_remove`.

References:
- https://developers.home-assistant.io/
- https://github.com/home-assistant/core/tree/2026.2.3/homeassistant
- https://developers.home-assistant.io/docs/core/entity/calendar
- https://www.home-assistant.io/actions/waze_travel_time.get_travel_times/
- https://www.home-assistant.io/integrations/waze_travel_time/
- https://www.hacs.dev/docs/publish/integration/

HACS layout: one custom_components domain, versioned manifest, codeowners, documentation, issue tracker, root hacs.json and README. External publication/acceptance is not implied by local validation.
