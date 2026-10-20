# Predicted versus actual mileage dashboard

The five existing forecast sensors are unchanged. For daily charts, enable the
**Mileage timeline** entity on your vehicle's device page (Settings → Devices &
services → Mobility Forecast → vehicle → disabled entities). Copy its actual
entity ID into the examples below; `sensor.car_mileage_timeline` is an example.

Install **ApexCharts Card** separately through HACS Frontend and reload the browser.
It is optional, not a dependency of this integration. Paste these complete cards
into a manual dashboard card. No separate website or EV setup is involved.
The card inherits the Home Assistant theme. The browser and HA should use the
same timezone for the date labels. ISO timestamps include the local UTC offset;
never replace them with fixed 24-hour increments across DST.

## Last 30 completed local days

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Car — predicted vs actual mileage
graph_span: 30d
span:
  end: day
  offset: -1d
apex_config:
  chart:
    stacked: false
  plotOptions:
    bar:
      columnWidth: 70%
  legend:
    show: true
series:
  - entity: sensor.car_mileage_timeline
    name: Predicted
    type: column
    unit: km
    color: '#5B8FF9'
    data_generator: |
      return (entity.attributes.history || []).map(r =>
        [new Date(r.timestamp).getTime(), r.predicted_km]);
  - entity: sensor.car_mileage_timeline
    name: Actual (observed)
    type: column
    unit: km
    color: '#38A169'
    data_generator: |
      return (entity.attributes.history || []).map(r =>
        [new Date(r.timestamp).getTime(), r.actual_quality === 'observed' ? r.actual_km : null]);
  - entity: sensor.car_mileage_timeline
    name: Actual (estimated)
    type: column
    unit: km
    color: '#E5A229'
    data_generator: |
      return (entity.attributes.history || []).map(r =>
        [new Date(r.timestamp).getTime(), r.actual_quality === 'estimated' ? r.actual_km : null]);
```

Missing predictions/observations are `null`, not zero. Estimated actual values
have a separate legend/color and are excluded from strict accuracy metrics.
The first genuine prediction appears only after the first successful 23:55
capture and the target day has completed. Installing the integration does **not**
generate predictions for the preceding month. Legacy predictions are not shown
as verified forecasts.

## Next 30 local dates (including today)

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Car — future mileage
graph_span: 30d
span:
  start: day
series:
  - entity: sensor.car_mileage_timeline
    name: Forecast
    type: column
    unit: km
    color: '#5B8FF9'
    data_generator: |
      return (entity.attributes.forecast || []).slice(0, 30).map(r =>
        [new Date(r.timestamp).getTime(), r.predicted_km]);
```

Use `graph_span: 7d` and `.slice(0, 7)` for a shorter view. Today is a full-day
prediction, not an observation of driving so far. Live forecasts may legitimately
change with new mileage, confirmed calendar edits, or time progression; refreshing
an unchanged calendar must not remove its contribution temporarily.

## Automations / Developer Tools actions

Use the config-entry selector to choose the vehicle:

```yaml
action: mobility_forecast.get_history
data:
  entry_id: YOUR_VEHICLE_CONFIG_ENTRY_ID
  days: 30
response_variable: mileage
```

`get_history` returns `entry_id`, `timezone`, `history` and `accuracy` (7, 30, 90).
`get_forecast` accepts the same selection and returns `entry_id`, `calculated_at`
and `forecast` with local `date`, offset-aware `timestamp`, `predicted_km`,
`low_km`, `high_km`. These are response-only read actions, not HTTP endpoints.
History can be requested for 1–365 days; the entity carries only 30 days.
No calendar titles, locations or coordinates are returned.

The timeline's large attributes are excluded from Recorder by the integration;
these charts read its current attributes, not Recorder history. Do not copy the
arrays into every forecast entity or template sensor. Inspect the entity's
`accuracy` attribute for MAE and bias, or use the action in automations.

Validation: the response/attribute contract, persistence and date alignment are
tested in-process with HA 2026.10.2. The JavaScript generators are executable
examples, but graphical rendering in a real Lovelace browser has **not** been
verified locally. ApexCharts is third-party software; report card version and
browser timezone when reporting display issues.

## Optional EV charging forecast

See [EV setup, assumptions, provider limits and native dashboard](ev.md). EV is
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
