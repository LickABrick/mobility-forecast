# API verification

Primary target/minimum: Home Assistant Core **2026.10.2**, Python **3.14.2**. Installed from `https://pypi.org/simple` using a uv-managed isolated `.venv314`. Original tests also passed against 2026.2.3/Python 3.13.5 before hardening; that older version is no longer the declared supported target.

The previous `pip index versions` ran under Python 3.13 and filtered releases requiring Python >=3.14.2. No custom pip index was configured. The absence from that listing was a Python compatibility filter, not evidence that 2026.10 was unavailable.

Verified against installed 2026.10.2 source:
- recorder history `get_significant_states` returns entity-keyed states, accessed using recorder's executor, never direct database writes.
- recorder statistics `get_metadata(hass, *, statistic_ids=...)`, `statistics_during_period(hass,start,end,ids,period,units,types)`; only physical `state`, not `sum`, is ingested.
- calendar.get_events response action uses start_date_time/end_date_time and entity targets; response is keyed by entity ID with an events list.
- Waze get_travel_times accepts origin/destination/region/realtime/vehicle_type/units and returns routes with distance and duration. Regions: us, na, eu, il, au; requested metric distance in km, duration minutes.
- `hass.services.async_call(..., blocking=True, return_response=True)` retrieves action responses.
- ConfigEntry runtime_data, background task creation, unload callbacks, options/reconfigure flow and Store delayed/atomic persistence remain available.

References:
- https://developers.home-assistant.io/
- https://github.com/home-assistant/core/tree/2026.10.2/homeassistant
- https://developers.home-assistant.io/docs/core/entity/calendar
- https://www.home-assistant.io/actions/waze_travel_time.get_travel_times/
- https://www.home-assistant.io/integrations/waze_travel_time/
- https://www.hacs.dev/docs/publish/integration/

In-process tests are not production server or live Waze verification. HACS structure and local metadata validation do not imply catalog acceptance.
