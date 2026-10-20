# Native configuration walkthrough

Initial setup is unchanged: **Add your vehicle** → optional **Vehicle name**, required **Odometer sensor** → submit. Invalid sources show “Select a numeric cumulative vehicle odometer with km or mi units, not a range or trip sensor.” Calendars/routing are never required here.

**Configure → Vehicle settings** has three menu choices:
- **Vehicle**: edit **Vehicle name**, submit.
- **Calendars**: multi-select **Calendars**, optional **Use Waze for routes**, submit. With routing off this completes immediately. With routing on, a second **Waze region** screen asks **Region**, with any previous selection retained. A missing provider shows “Install Waze Travel Time before enabling routes.” The calendar form explains that locations go to an external service, not event titles.
- **Known locations**: optional exception management. **Add location** asks **Location name in calendar** and **Address or coordinates**. **Edit location** selects an existing name then displays the same editable fields. **Remove location** selects one existing name and submits. There is no JSON/object editor. Invalid addresses show “Enter a full address with street number and city, or valid coordinates.” Duplicate names direct the user to Edit location. Existing mappings from the original release remain compatible.

**Reconfigure** changes the mandatory source. History stays stored, source continuity is checked before accepting replacement data. Unknown or incompatible sources are not silently merged. Removing calendars or changing settings never deletes history. Vehicle removal deletes only Mobility Forecast-owned state.

Dutch translations provide matching menus, fields, privacy notices and errors. Normal users never configure statistical thresholds, cache timers or model weights.

## Testing without a connected car

Create a Number helper (Settings → Devices & services → Helpers), called **Demo odometer**, with minimum 0, maximum 1000000, step 1 and unit km. Set it to 10000. Then create a Template sensor helper whose state template is:

```jinja
{{ states('input_number.demo_odometer') }}
```

Set unit **km**, device class **Distance**, state class **Total increasing**. Alternatively use YAML:

```yaml
template:
  - sensor:
      - name: Demo vehicle odometer
        unique_id: demo_vehicle_odometer
        unit_of_measurement: km
        device_class: distance
        state_class: total_increasing
        availability: "{{ is_number(states('input_number.demo_odometer')) }}"
        state: "{{ states('input_number.demo_odometer') }}"
```

Choose `sensor.demo_vehicle_odometer` in Mobility Forecast. Add distance to the helper after simulated journeys (10000 → 10030 → 10075), leave unchanged when parked, never reset it at midnight. Leave Recorder enabled. No immediate numeric forecast is expected: at least seven usable completed days are needed, and regular fresh observations improve coverage. This is a source-behavior test, not instant historical backfill. Remove the demo vehicle and helper after testing; do not reuse its history for a real car.

## Visibility and source recovery

The vehicle device page should contain five forecast sensors immediately. Initial `unknown` values are normal. If the integration card says **Failed to set up**, open its logs; successful configuration alone does not prove platform setup succeeded. User-disabled registry entities must be explicitly enabled on the device page. Reload after enabling where HA requests it.

Repeated decreases on two distinct UTC dates create a reset-counter Repair and `source_incompatible`; valid stored history is retained, but predictions are withheld. One decrease is rejected as a possible telemetry glitch, not definitive reset evidence. `total_increasing` metadata alone is not proof of suitability. Reconfigure to a continuous cumulative source to recover; old incompatible intervals are never stitched into a new mileage total.

## Ignore nested appointments (optional)

Configure → Calendars includes **Ignore nested appointments** / **Geneste afspraken negeren**, default off for both existing and new vehicles. No migration or new setup step is needed. It applies across all selected calendars after normalization/deduplication.

Worked example:

```text
08:00–12:00 Maintenance at Customer A
09:00–09:45 Ticket at Customer B
10:00–10:30 Ticket at Customer C

Nested filtering ON:
Home → Customer A → Home

Nested filtering OFF:
Existing conservative overlap behavior (incomplete day, historical fallback)
```

The retained parent must have a valid physical location and strictly longer duration, fully containing the child by timestamp. Same-time appointments and partial overlaps remain conflicts. Missing-location children can be ignored by valid parents. All-day, locationless and overnight containers cannot suppress trips. Clearly virtual events are excluded separately; ambiguous physical locations remain unresolved. Same-location merging still avoids unnecessary journeys.

A genuinely separate journey fully contained in a longer visit is also ignored when enabled. Use the setting only when this interpretation matches your calendars. Turning it off restores strict overlap behavior. Any calendar/route/location/nesting options change starts a fresh generation; odometer history and valid hashed route-cache entries are retained.

## Known Locations and route reuse

`Office → Main Street 10, Arnhem` makes Office and that exact physical address share a route identity, including case/whitespace/comma-spacing variants. Adding `6811 AB` is not automatically considered equivalent: define explicit mappings if you know both forms identify the same place. Different street/unit numbers remain distinct. Changing Office to a different address creates a different route identity; unrelated valid old cache entries remain until expiration/eviction. Region changes use separate keys. No cache duration/size configuration is needed.

## Locationless appointments

No setting is required: internal meetings, reminders, calls, unknown venue names and virtual events without recognized physical destinations are excluded before nested filtering. Known Locations can resolve an otherwise unknown venue. Ignored events between customer visits do not split a chain into separate round trips. A locationless ticket is counted as locationless, not nested; a physical contained ticket is counted as nested only when that option is enabled. Skipping an event is not evidence of zero real travel.

## Daily comparison data

No new required settings. Enable the optional **Mileage timeline** sensor on the
vehicle device for the [dashboard examples](dashboard.md). It has no state class
or distance unit: its state is model status, with bounded history/forecast
attributes. The five existing distance sensor unique IDs are unchanged.
`mobility_forecast.get_history` and `mobility_forecast.get_forecast` are read-only
response actions selected by config-entry ID. History accepts 1–365 days; the
timeline entity carries 30 completed days, future dates and 7/30/90 metrics.

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
