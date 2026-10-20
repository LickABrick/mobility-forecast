# Troubleshooting

## No entities appear

**Cause:** platform setup failed or entities were disabled. **Check:** vehicle device,
HA logs and entity registry. **Do:** reload after correcting setup; enable wanted
entities explicitly. Five mileage sensors register even while values are unknown.
Mileage timeline is disabled by default; enabling it does not invent earlier predictions.

## Forecast is unknown / not enough history

**Cause:** initialization, learning or missing usable observations. **Check:**
`forecast_status`, `history_import_status`, `history_days`. **Do:** allow import to
finish, verify Recorder includes the source and collect seven adequately covered days.
Unknown is not zero. `provisional` means weaker estimated evidence; `ready` means
supported mileage forecasting, not complete calendar routing or guaranteed accuracy.

## Odometer unavailable or counter reset

**Cause:** unavailable/non-numeric state, unsupported unit or repeated decreases.
**Check:** original vehicle integration and Repairs. **Do:** restore the source or
Reconfigure to a continuous lifetime odometer. Never use range/trip counters.
`source_unavailable` and `source_incompatible` withhold predictions while preserving
history. Do not delete storage to silence a Repair; back up before deliberate reset.

## Unexpectedly high or low forecast

**Cause:** sparse telemetry, changed usage, calendar journey or source semantics.
**Check:** history quality and calendar inclusion. **Do:** compare observed and estimated
days; do not mistake annual expectation for year-to-date distance. Unknown stationary
periods are not zero. No configurable model weights are needed.

## Forecast changes after restart

**Cause:** calendar verification or expired retained plan. **Check:** calendar status,
verification age and incomplete counts. **Do:** allow asynchronous verification or
Manual Sync. Freshness is two hours; compatible complete distances can persist
provisionally for 24 hours. Cancellation is authoritative; expired data falls back
to history. Numeric restoration does not establish EV journey timing.

## Calendar not included / Waze unavailable

**Cause:** routing off, missing Waze action, failed calendar, unresolved location or
incomplete itinerary. **Check:** selected calendars, region, `calendar_status`,
last-success/failure and pending/incomplete counts. **Do:** verify Waze Travel Time,
resolve known locations and wait for bounded retries. `disabled` is intentional;
refreshing/pending work is not complete; cached/provisional/stale data needs verification.
Transient provider outages do not require a persistent Repair.

## Some appointments ignored

**Cause:** virtual/locationless/unrecognized event, unsupported all-day/overnight,
physical overlap or nested filtering. **Check:** aggregate ignored counts and calendar
semantics. **Do:** use [known locations](calendar-routing.md#known-locations); turn off
nested filtering if contained appointments represent genuine separate journeys.
Skipped appointments are not proof of no travel.

## Mileage Timeline has no history

**Cause:** disabled entity or no genuine pre-day snapshots. **Check:** registry and
23:55 capture availability. **Do:** enable the entity, allow completed local days and
use [dashboard examples](dashboard.md). Missing predictions are not backfilled.

## Manual sync fails

**Cause:** unavailable input, provider failure, shutdown or timeout. **Check:** switch
status/timestamps/`last_error_code` and calendar/EV statuses. **Do:** fix source problems,
wait out cooldowns and retry. Switch-on is nonblocking; user-off does not cancel work.
The waiting action raises on failure. Success does not guarantee every route is complete.

## EV battery data unavailable

**Cause:** missing, stale, wrong-unit or out-of-range SoC. **Check:** percent sensor and
freshness. **Do:** restore telemetry; do not substitute zero. Disable EV if not wanted.
Mileage forecasting remains independent.

## No suitable charging opportunity / public provider unavailable

**Cause:** insufficient timing, unreachable reserve shortfall, inadequate session,
missing consent or rejected provider data. **Check:** EV reason/status and charging mode.
**Do:** verify physical inputs and known opportunities. Do not interpret missing advice
as no charging needed. NDW unit ambiguity can exclude points; no availability is guaranteed.
See [EV limitations](ev-charging.md#limitations).

## Upgrade problems

**Cause:** partial file replacement or unsupported/corrupt storage. **Check:** installed
version, logs and Repairs. **Do:** restore a backup or replace the complete integration
directory and restart. Preserve private storage. Never edit it while HA is running.

## Logs and sanitized diagnostics

Use Settings → Devices & services → Mobility Forecast → Download diagnostics, and
Settings → System → Logs. Enable debug logging from the integration menu only while
reproducing. Review exports before sharing. Report versions, installation method,
features, sanitized failure category and reproduction steps. Never post raw calendar
payloads, addresses, coordinates, vehicle identifiers, credentials or private stores.
`error` is not proof of data loss; storage Repairs stop writes to preserve unreadable data.
