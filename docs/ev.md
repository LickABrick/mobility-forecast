# Optional EV charging forecasts

This feature estimates charging needs, not automatic charging control, navigation,
reservations, tariffs or solar optimization. Existing non-EV vehicles are unchanged.

## Setup

Open the vehicle's integration options → **Electric vehicle / Elektrisch voertuig**.
Enable EV forecasts, select a percent battery sensor, enter **usable** capacity in
kWh (not nominal), typical battery consumption in kWh/100 km, and maximum vehicle
AC power in kW. These three values have no guessed defaults. Select:

- **Home only / Alleen thuis**: only the configured home window, no external lookup.
- **Home and appointments / Thuis en bij afspraken**: home plus nearby public AC.
- **Appointments only / Alleen bij afspraken**: never assumes home charging.

Preferred limit defaults to 80%; reserve defaults to 15%. Public discovery requires
explicit consent: destination address goes to PDOK and coordinates go to NDW; no
appointment title/description is sent. Disable EV or choose home-only to stop it.

Advanced defaults: minimum appointment 90 minutes, maximum straight-line distance
300 m, connection/disconnection overhead 15 minutes, useful-session preference
5 kWh, prefer longer sessions enabled, home 18:00–07:00, above-preferred targets
disabled, absolute limit 100%. Appointment duration/radius are hard filters;
small-session and longer-session preferences cannot justify missing a reserve
requirement. Current scheduler adds only necessary energy; the useful-energy
preference is reserved for further ranking refinement, not a safety blocker.

Additional vehicle data is optional: reported range (km/mi), charging power (W/kW),
vehicle limit (%), remaining duration (s/min/h), consumption (kWh/100km or Wh/km),
energy added (Wh/kWh), charging state, cable state and vehicle home/away state.
Selections are manual; same-device suggestion assistance is not yet implemented.
Supported charging text: charging/laden/on, paused/gepauzeerd, faulted, completed,
stopped/off/connected. Other states remain unknown; connected does not mean charging.

## Energy and time

Driving energy = distance × battery consumption / 100. Reserve-aware range excludes
capacity × reserve / 100. AC charging uses **90% efficiency** once: grid kWh =
battery kWh / 0.9; duration = grid kWh / minimum(vehicle AC kW, connector AC kW).
Unknown/DC-only power is never treated as unlimited. Charging targets respect the
preferred limit, or the smallest necessary exceptional target only with explicit
permission, bounded by absolute and vehicle-enforced limits. No commands are sent.

SoC must be finite, 0–100%, and reported within six hours. Detected driving after
the SoC observation makes it uncertain. A journey already in progress cannot be
reliably replayed from a mid-journey anchor. Unknown battery data is not zero.
Optional live state is exposed; direct vehicle time-to-target is **not** currently
used because its target semantics cannot be verified from an arbitrary entity.
Live-power current-session recalculation is not yet implemented.

## Planning and limitations

Maximum horizon: seven local dates including today. The existing Waze daily chain
now exposes legs and stops without extra requests. Physical timed stops must have
a valid complete itinerary. Short, virtual, locationless and ignored nested events
cannot become public charging stops. AC only: Type 2, known sensible power,
open/public indication, radius filter and sufficiently recent infrastructure data.

The deterministic planner finds the earliest reserve shortfall and considers
reachable windows before it. It rejects travel overlaps, inadequate duration and
excessive targets. Later feasible windows and longer useful sessions are preferred.
It returns one next action and at most one alternative, not a full multi-session
optimizer. A recommendation covers the relevant segment, not a guarantee that a
single session satisfies the entire week.

Home availability is assumed from the configured window and home-to-home calendar
chain; an explicit current away state excludes the current home opportunity.
Historical-only days use an **estimated day-end energy debit**, not a genuine
journey departure. Today's unknown remaining mileage is not replayed from midnight.
Thus coarse planning may understate current-day demand and never has timed confidence.
Appointment-only mode without timed legs returns insufficient information.

## Providers and privacy

PDOK Locatieserver v3_1 `/free`, verified from its current OpenAPI on 2026-10-20,
uses address-only results. V1 conservatively requires a Dutch postcode plus exact
house number/letter; disagreement is ambiguous, not automatically accepted.
Coordinate aliases (including resolved HA zones) bypass geocoding. Explicit foreign
country names are rejected. International destinations are not supported.

NDW DOT-NL GeoJSON v1 `/features?bbox=...` was inspected against official OpenAPI
0.0.2 and a live small-area response on 2026-10-20. Important provider mismatch:
schema says `power_max` is **kW**, live response contained **15000** for AC. Such
values are rejected, not silently divided by 1000. Consequently many real points
may be unavailable until provider semantics are clarified. `open: false`, unknown
power, stale timestamps and incompatible/DC connectors are rejected conservatively.
Public availability is never guaranteed tomorrow. Cached occupancy becomes unknown.
Distance is straight-line, **not walking distance**; public points need not be in
customer parking. No reservation is implied.

Credits: [PDOK](https://www.pdok.nl/) / Kadaster and
[NDW DOT-NL](https://docs.ndw.nu/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/).
Both provider contracts may change.

Per vehicle: serialized HTTP calls at most one per second, eight-second timeout,
512 kB response cap, 429 backoff five minutes, 128 hashed cache records; validated
geocodes 30 days, negatives one day, charger locations one day. No raw provider
responses or calendar addresses are persisted by EV caching. Each discovery pass
examines at most ten unique destinations and thirty retained stops. Excess work is
reported deferred; automatic continuation through all excess destinations is not
yet implemented. No lookup is caused solely by a SoC change when the agenda lookup
signature and one-day lookup freshness are unchanged. Failed lookups currently
retry at the next day/signature change, not continuously. Vehicle removal uses the
existing per-entry store deletion. EV disable stops tasks; existing bounded cache
is retained for reuse rather than immediately erased.

## Native dashboard (no plugin)

Replace these example entity IDs with those on your vehicle device:

```yaml
type: entities
title: Car — mobility and charging
entities:
  - entity: sensor.car_battery
    name: Current battery level
  - entity: sensor.car_estimated_range_above_reserve
  - entity: sensor.car_expected_distance_tomorrow
  - entity: sensor.car_next_suggested_charging_time
  - entity: sensor.car_recommended_charging_target
  - entity: sensor.car_recommended_battery_energy
  - entity: sensor.car_estimated_charging_duration
  - entity: sensor.car_charging_forecast_status
```

Native cards inherit light/dark themes. Entity IDs depend on device names; stable
unique IDs are `<entry_id>_ev_estimated_range`, `_ev_next_charge_start`,
`_ev_target_soc`, `_ev_charge_energy_needed`, `_ev_estimated_charge_duration`,
`_ev_charge_forecast_status`. No long-term-statistics state class is assigned to
these changing recommendations. Status reason/confidence are on the status sensor.

`mobility_forecast.get_ev_plan` is response-only:

```yaml
action: mobility_forecast.get_ev_plan
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
  horizon_days: 7
response_variable: ev_plan
```

Response schema 1 includes status, configuration summary, freshness, demand,
reserve-aware range, recommendation, alternative, shortfall and at most 24 windows.
The optional requested horizon is currently bounded/validated but output always
uses the fixed seven-day plan. No raw private calendar data is returned.

Status: ready, estimated, no_charge_needed, insufficient_data, no_feasible_window,
provider_unavailable; disabled is returned by the action for non-EV entries.
Check `reason`: stale/unavailable SoC, insufficient history/timing, incomplete
itinerary or unreachable reserve shortfall. No charge needed is not a battery-data
error. Missing recommendations must not be converted to zero charging energy.

This is an initial supervised-test implementation, **not production-certified**.
Mocked automated tests do not cover every requested lifecycle/scheduling scenario.
No real vehicle charging session or graphical dashboard walkthrough was performed.

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

## Project branding

The [Mobility Forecast brand assets](../assets/brand/README.md) include transparent
icons and light/dark wordmarks. They are repository presentation assets, not an
automatically installed Home Assistant integration tile.
