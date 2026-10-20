<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-dark.svg">
    <img src="assets/brand/logo.svg" alt="Mobility Forecast — route and prediction mark" width="480">
  </picture>
</p>

# Mobility Forecast

Local, explainable travel predictions for your Home Assistant vehicles.

[Brand assets and usage](assets/brand/README.md) · [Manual sync](docs/configuration.md#manual-sync)

## Finding your forecasts

After adding a vehicle, open **Settings → Devices & services → Mobility Forecast → your vehicle**. Five enabled distance sensors are created even while learning: expected distance today, tomorrow, next 7 days, next 30 days and annual distance (names follow your HA language). Developer Tools → States lists their `sensor.*` entity IDs; registry IDs may reflect your vehicle name and previous renames.

Initial values can be `unknown`. Inspect `forecast_status`, `history_days`, `history_import_status` and `calendar_status` in state attributes. `learning` means insufficient usable history, not missing entities. `source_unavailable` means the source is missing/nonnumeric; `source_incompatible` means repeated resets were detected. Check Repairs and [troubleshooting](docs/troubleshooting.md) for recovery. Entities you previously disabled remain disabled.

Use a lifetime cumulative vehicle odometer, never daily walking/running distance, range or a resettable trip counter. You can [test without a connected car](docs/configuration.md#testing-without-a-connected-car) using a standard HA helper/template sensor.

Local, explainable distance forecasts for individual vehicles in Home Assistant.

**Version 1.0.0 — minimum and primary tested Home Assistant Core: 2026.10.2; Python 3.14.2+.** See [API verification](docs/api-verification.md).

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
2. Open Mobility Forecast's **Configure → Calendars** options for the vehicle.
3. Select one or more calendars. Enable **Use Waze for calendar routes** only if you consent to sending origin/destination locations to Waze.
4. Select the correct Waze region (`eu`, `us`, `na`, `il`, `au`). No region is inferred silently for requests.
5. Optionally open **Configure → Known locations → Add location**, enter a calendar location name and its coordinates or complete address. No JSON editing is required. HA zones and home are recognized automatically.
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
- Retention: three years of compacted physical observations (first/last per hour), independent of telemetry frequency. Initial import can still take time; raw recorder queries use six-hour batches.
- Periodic reads use the sensor’s actual last-reported timestamp; truly stale sensors remain uncertain.
- Calendar refresh is periodic (30 minutes), not push-based. Midnight recalculation is scheduled separately.
- Arbitrary venue names require a zone or explicit known-location mapping. All-day and cross-midnight events are excluded from concrete route totals.
- Source resets are rejected rather than silently rebased. Live entity renames require reload to resolve registry identity.
- Region must be selected explicitly. Route request budget is 60 per work cycle, with at most three independent daily chains running concurrently and a 45-second work-cycle deadline. Historical predictions never wait for routing. Cache holds at most 512 entries for seven days.
- Partial-day allocation assumes uniform travel throughout the day; no hour-of-day precision is claimed.
- Schema v1 is versioned; unsupported future/corrupt storage is preserved rather than overwritten. No historical pre-v1 schema is supported.
- Local tests are not HACS catalog acceptance or live Waze verification. Hassfest passes; HACS validation needs a GitHub token. See [validation report](docs/validation.md).

### Large calendars and nested tickets

Calendar routes are calculated progressively: today first, then upcoming days, with up to three daily chains running at once. Completed days remain usable if later work times out. Pending work resumes after a one-minute pause; failed/incomplete days use historical forecasts and are reconsidered at the next regular refresh. Calendar overlays never add planned kilometers on top of the historical baseline: the conservative maximum is used.

**Configure → Calendars → Ignore nested appointments** is off by default. Enable it if shorter tickets inside a longer physical visit should not create separate journeys, even at different addresses. This also ignores a genuinely separate trip inside that visit; it is an interpretation preference, not proof that appointments belong together.

Inspect `calendar_status`, `calendar_events_count`, `calendar_nested_ignored`, `calendar_days_complete`, `calendar_days_pending`, `calendar_days_incomplete`, `calendar_requests`, `calendar_last_success` and `calendar_last_failure` on existing forecast entities. No event titles or addresses are exposed.

### Route cache

Successful Waze routes are cached per vehicle for seven days, up to 512 directed routes. Identical pending requests share one calculation; completed routes are reused across days, continuation cycles and restarts. Origin/destination order and Waze region remain distinct.

Known Locations aliases resolve before routing. Casing, whitespace, comma spacing and equivalent coordinate spellings share identities; different house numbers, postal codes and precise coordinates do not. No fuzzy matching or automatic geocoding is performed. Use an explicit alias when you know two representations identify the same place.

Diagnostics include last-cycle cache hits, misses, expiration, deduplication, eviction and actual Waze calls/failures, without endpoints or cache keys. Four aggregate values also appear on existing forecast sensors; no extra sensors or cache settings are added. Seven-day-old route durations may be inaccurate after road changes and do not represent live traffic.

### Calendar reliability

Only appointments with recognized physical destinations contribute routes. Locationless, unrecognized-location and clearly virtual events are automatically skipped, without invalidating other customer visits. This does **not** prove those activities involve no travel: calendar mileage estimates only known routable appointments and never replaces the historical baseline with a guaranteed zero.

Malformed individual events are skipped and counted; a missing calendar or invalid service-response container remains a retrieval error. Temporary Waze failures retry with bounded backoff. Physical overlaps and impossible travel schedules remain incomplete and use historical mileage. Inspect `calendar_events_without_location`, `calendar_events_virtual_skipped`, `calendar_events_invalid_skipped` and `calendar_last_failure` for aggregate explanations.

## Stable forecasts and mileage comparisons

Calendar synchronization retains committed plans while retrieving unchanged agendas,
uses hashed daily itinerary identities, and routes only changed days. Optional
**Mileage timeline** and response actions provide predicted-versus-actual mileage.
See [dashboard setup](docs/dashboard.md). Verified predictions start with the first
successful 23:55 local pre-day capture; past predictions are never fabricated.

## Optional EV charging forecast

See [EV setup, assumptions, provider limits and native dashboard](docs/ev.md). EV is
disabled by default and never controls the vehicle or charger. Existing mileage
entities, history and calendar synchronization remain independent.

## Restart and EV remediation update

Complete calendar distance overlays are now stored separately from Waze route
cache entries. Startup restores validated, configuration-compatible plans before
the first forecast calculation, for up to two hours since agenda verification.
Stored records contain hashed fingerprints/config identity, dates, distances and
verification/routing times, not addresses or stops. Old storage needs no migration.
Restored data is labeled cached pending asynchronous verification. EV timing must
be rebuilt from the agenda; a numeric restored overlay is not a timed itinerary.
Failed startup retrieval uses 10/30/60/120-second retries then normal 30-minute
checks, rather than treating failure as successful retrieval. Routing identity
excludes unrelated EV options.

EV demand now reconciles full forecast distance with timed legs and measured
minimum movement today; remaining mileage is explicitly unallocated estimated
demand. Its day-end debit remains a coarse assumption, not exact travel timing.
Home windows preserve both sides of away intervals. Postcode-free Dutch addresses
require exact street, house number and municipality/locality. NDW ambiguous power
units remain fail-closed; no new evidence justifies automatic watts conversion.
Discovery progresses through ten unique destinations per pass, retaining completed
results and bounding temporary-failure retries. Revision tracking prevents old EV
calculations from publishing after inputs change. Response horizons filter windows
and demand while explicitly retaining a seven-day internal calculation horizon.

Validation evidence: reconstructed-store HA entry reload reproduces 95 km before,
95 km while calendar fetch is blocked after reload, and 95 km after verification.
This is in-process HA testing, not a real HA process restart. The 30/150/300
fixtures now process all destinations across bounded passes rather than starving
entries after the first ten. Full suite: 218 passed. The full requested restart,
race, session and DST matrices are not yet covered; multi-session scheduling,
coarse-day timing and provider semantics remain supervised-test limitations.
