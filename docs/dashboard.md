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
