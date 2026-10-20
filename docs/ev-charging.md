# Optional experimental EV charging estimates

EV is disabled by default. This feature never controls a vehicle or charger and does
not provide tariffs, reservations, navigation or a full weekly charging optimizer.

## Setup

Open Electric vehicle → EV setup. Select a percent battery sensor, usable battery
capacity (not nominal capacity), typical battery consumption in kWh/100 km and maximum
vehicle AC power. Those physical values have no guessed defaults. Reserve defaults
to 15%, preferred maximum to 80%. Modes are Home only, Home and appointments, and
Appointments only. Disabling EV preserves its saved settings.

Public charging requires explicit external-lookup consent. Home-only mode does not
query PDOK/NDW. Calendar routing consent is separate.

## Advanced options

Minimum appointment duration (90 minutes) and maximum straight-line charger radius
(300 m) are hard filters. Session overhead defaults to 15 minutes. Minimum useful
energy (5 kWh) and preference for longer sessions are soft ranking preferences, not
permission to ignore reserve or reachability. Home window defaults to 18:00–07:00;
overnight windows are supported. Higher-than-preferred targets require explicit
permission and remain bounded by the absolute maximum and reported vehicle limit.
Hidden mode-specific values are retained when switching modes.

## Vehicle entities

Optional numeric telemetry includes range (km/mi), charging power (W/kW), enforced
charge limit (%), remaining time (s/min/h), consumption (kWh/100km, kWh/100 km, Wh/km)
and added energy (Wh/kWh). State/cable/location entities are optional too. Review
suggestions; selecting an entity is not proof of its semantics. Saved manual choices
are never overwritten. Unknown/unavailable readings remain unknown.

The enforced limit and home/away evidence constrain planning. Live power can inform
active home charging estimates. Reported range and remaining duration are context;
arbitrary time-to-target does not reveal the target. Added energy is not used by the
planner. Do not assume every optional entity improves mileage or energy predictions.

## Energy and duration

Battery energy equals distance × configured consumption / 100. Reserve-aware range
excludes reserved battery energy. AC duration applies 90% efficiency once and is
limited by vehicle and known connector power. Unknown/DC-only power is not unlimited.
SoC must be finite, 0–100%, and reported within six hours; detected driving after the
observation adds uncertainty. Unknown data is never zero.

The planner finds the earliest reserve shortfall and a reachable earlier window,
returning one next action and at most one alternative. Home availability is assumed
from the configured window and reconstructed journeys; current away evidence requires
a known return. Untimed forecast mileage stays separate from genuine journey legs.
Reserve risk without reliable departure timing withholds precise advice.

## Providers and privacy

PDOK geocodes Dutch addresses with conservative exact matching; coordinates and zones
bypass geocoding. International destinations are not supported. NDW supplies nearby
public AC infrastructure. Destination addresses go to PDOK and coordinates to NDW,
not titles/descriptions. Hashed bounded caches retain validated results, not raw events.
Discovery progresses across bounded passes; transient failures have bounded retries.

NDW schema declares kW, while inspected live AC data reported values such as 15000.
Ambiguous power is rejected, never guessed to be watts. Public access semantics also
need caution. See [contract evidence](ndw-contract.md). Radius is straight-line, not
walking distance. Infrastructure presence does not guarantee availability or reserve
a connector. Provider failure is not a zero-energy recommendation.

## Status and actions

Statuses retain `ready`, `estimated`, `no_charge_needed`, `insufficient_data`,
`no_feasible_window`, `provider_unavailable`. Inspect reason and freshness attributes.
Ready means an estimate is available, not that a public charger is reserved.

`get_ev_plan` is read-only and makes no external requests. Its internal assessment
covers seven local dates. Shorter responses filter demand/windows but deliberately
withhold recommendations and assessment, with `filtered_not_recalculated` scope.
They are not independently optimized short-horizon plans. See [actions](developer/actions.md).

## Limitations

This is an experimental first-action heuristic. Coarse historical demand has no exact
departure time; restored numeric calendar overlays are not trusted timed itineraries.
Public power/access ambiguity may exclude many points. Mocked tests are not real
vehicle certification. No real charging session or HAOS graphical staging is claimed.
See [staging procedure](developer/staging-validation.md) before relying on advice.

For a native dashboard use the [Entities example](dashboard.md); additional frontend
components are optional. Missing recommendations must not be converted into zero.

## Learning and diagnostics

Calendar-only mileage does not establish complete EV demand. EV remains insufficient_data
until supported mileage evidence exists; unknown demand is never zero charging need.
See [sync and forecast diagnostics](sync-diagnostics.md).
