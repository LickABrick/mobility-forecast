# Mobility Forecast

Local, explainable distance forecasts for individual vehicles in Home Assistant.

**Version 1.0.0 — minimum and locally tested Home Assistant Core: 2026.10.2; Python 3.14.2+.** The requested 2026.10 build was not available in this environment; compatibility with it is not yet verified. See [API verification](docs/api-verification.md).

## Install

1. In HACS, open **Custom repositories**, add `https://github.com/LickABrick/mobility-forecast`, category **Integration**, and download Mobility Forecast. This repository is not claimed to be in the default HACS catalog.
2. Alternatively, copy `custom_components/mobility_forecast` into your HA configuration's `custom_components` directory.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Mobility Forecast**.
5. Select a cumulative vehicle odometer, optionally give the vehicle a name, and finish. Repeat for another vehicle.

No external account or calendar is needed for historical predictions. History imports in the background. Initially sensors may be unknown, not zero. At least seven adequately covered days are needed. The five sensors appear under a separate logical vehicle device.

## Supported sources

Numeric sensors in `km` or `mi` with cumulative state class (`total` or `total_increasing`) or a recognizable odometer name. Range and trip sensors are rejected. State class alone cannot prove that a sensor is an odometer: select the vehicle's lifetime mileage, not another cumulative distance counter. The source must have an available numeric state at setup. Internally all distances are kilometers; HA may display converted units.

Up to three years of recorder and suitable physical-state long-term statistics are imported in bounded queries. Recorder must have recorded the source; excluded or purged data cannot be recreated. Statistics `sum` is never mistaken for actual mileage. Current samples and history are retained in a per-vehicle Home Assistant storage file with debounced atomic writes.

## Predictions

- **Today**: expected full local calendar-day distance, at least the known distance driven within that day.
- **Tomorrow**: next local calendar day.
- **Next 7 / 30 days**: rolling period starting now, with proportional partial-day allocation, not eight or thirty-one full days.
- **Annual**: forward-looking 365-day historical expectation, not distance driven this year.

Unknown days are not zero. Fresh unchanged observations can support genuine stationary periods; a stale state alone cannot. Multi-day intervals are distributed as **estimates**, not assigned to the last day. Forecasts use robust averages, supported weekday patterns and a bounded recent trend. Indicative ranges are not calibrated confidence intervals. See [algorithm](docs/forecasting.md).

## Optional calendars and Waze

1. Add **Waze Travel Time** using Home Assistant's built-in integration. Confirm the `waze_travel_time.get_travel_times` action exists.
2. Open Mobility Forecast's **Configure** options for the vehicle.
3. Select one or more calendars. Enable **Use Waze for calendar routes** only if you consent to sending origin/destination locations to Waze.
4. Select the correct Waze region (`eu`, `us`, `na`, `il`, `au`). No region is inferred silently for requests.
5. Optionally map ambiguous names to coordinates or a complete address in **Known locations**, e.g. `{"Office": "52.12345,5.12345"}`. HA zones and home are recognized automatically.
6. Check `calendar_status` and `calendar_included` sensor attributes after refresh (normally within 30 minutes).

Valid appointments form one chronological `home → appointment → appointment → home` journey. Forecasts use **max(historical baseline, known planned route kilometers)**, never blindly add them. Missing/overlapping/all-day/overnight itineraries are conservative and may fall back entirely to history. No inference establishes which car was actually used. Annual predictions do not multiply one-off agenda journeys.

Disable routing or deselect calendars at any time. Historical data is preserved.

## Privacy

History/model/persistence run locally. Only explicitly enabled Waze routing transmits coordinates or addresses, not event titles/descriptions/attendees. Calendar titles/descriptions are not persisted. Route cache keys are hashes but histories, aliases and cached distances remain sensitive data in HA backups. Downloaded diagnostics omit addresses, coordinates, source IDs and raw history. No external backend or telemetry is added.

## Configuration and maintenance

Use **Reconfigure** to change an odometer. Existing history and entity unique IDs are preserved. A discontinuous replacement is not merged automatically; repair the source or deliberately remove/re-add the forecast vehicle to start a new history. Original sensors, calendars, Waze and recorder history are never deleted. Removing the vehicle removes its Mobility Forecast storage.

See [configuration](docs/configuration.md), [troubleshooting](docs/troubleshooting.md), [architecture](docs/architecture.md).

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python scripts/validate.py
```

Tests mock external routing and recorder responses; the HA fixture smoke test exercises actual in-process setup/sensor/unload APIs. No live Waze or full production HA server smoke test is claimed.

## Limitations

- No EV/charging features, GPS reconstruction or vehicle assignment.
- Retention: three years / 50,000 readings; imports can be expensive on the first run.
- Repeated unchanged reports without state-change events are not subscribed to directly. Recorder/fresh state changes provide the available brackets; truly stale sensors remain uncertain.
- Calendar refresh is periodic (30 minutes), not push-based. Midnight recalculation is scheduled separately.
- Arbitrary venue names require a zone or explicit known-location mapping. All-day and cross-midnight events are excluded from concrete route totals.
- Source resets are rejected rather than silently rebased. Live entity renames require reload to resolve registry identity.
- Region must be selected explicitly. Route request budget is 60 per refresh; cache holds at most 512 entries for seven days.
- Partial-day allocation assumes uniform travel throughout the day; no hour-of-day precision is claimed.
- Schema v1 is versioned; unsupported future/corrupt storage is preserved rather than overwritten. No historical pre-v1 schema is supported.
- Local tests are not HACS acceptance or a successful upstream Hassfest run. See [validation report](docs/validation.md).
