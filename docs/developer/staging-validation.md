# Real Home Assistant staging validation

**Not executed by writing this procedure.** Use a spare HAOS VM/installation on Core
2026.10.2, not a live vehicle automation environment. Record HA/integration versions,
exact commit SHA, date, timezone, result and sanitized evidence for each row below.
Take a full HA backup first. Disable unrelated vehicle/charger automations. Use fake
appointments and public/sample locations only. Never upload private stores or logs.

## Sample source

Create Number helpers for demo odometer (km, 0–1000000) and battery (%, 0–100).
Create Template sensor helpers exposing numeric values, device classes Distance /
Battery, units km / %, and cumulative odometer state class Total increasing. Start
odometer at 10000; add distance after journeys, keep reporting while parked. For
immediate history tests restore a sanitized staging backup with seven covered days;
do not forge production history. Use a second independent vehicle for isolation.

## Installation and upgrade

- Fresh HACS custom repository download → restart → add vehicle with no calendars/EV:
  five mileage entities and Manual Sync appear, unknown while learning, EV absent.
- Repeat on clean VM with manual full-directory installation. Check logs for setup errors.
- Upgrade a backed-up existing staging entry in place: compare config-entry ID,
  five unique IDs, disabled flags, options, readings and cached plans before/after.
  No duplicate entities, history reset or new migration should occur.
- Inspect light/dark integration tiles. In an authenticated browser request
  `/api/brands/integration/mobility_forecast/icon.png?placeholder=no`; expect actual PNG,
  not placeholder. Repeat logo/dark logo via HA frontend. File tests alone do not prove this.

## Restart and calendar matrix

For each case record first forecast, calendar status and post-verification result:
ordinary HA process restart, integration reload, blocked calendar, unavailable Waze,
3/8/24/25-hour downtime, Manual Sync after restart. Complete compatible overlays
remain provisional within 24 hours, expire beyond it, and never imply verified EV timing.

Use a dedicated test calendar: one physical appointment, several chronological visits,
partial overlap, fully contained sub-event (setting off/on), virtual meeting, missing
location, invalid address, all-day and overnight visit. Change/cancel an appointment:
authoritative cancellation removes its overlay; changed destinations reroute only
within bounded work. Watch pending/incomplete counts, not just mileage readiness.

## EV matrix

Enable EV with known test values; review each of three charging modes and native
number/time controls in English and Dutch. Verify overnight windows, saved advanced
values, disable/re-enable, reload and optional entity clearing. Two vehicles and an
unrelated home battery must not cross-link suggestions. Remove/rename optional entities
and confirm missing values stay unknown. Check below-reserve, missing/stale SoC,
current away state, unknown travel timing, no feasible session and provider outage.
Public infrastructure never guarantees occupancy/reservation. Do not execute charging
controls (none are provided). Real vehicle SoC/session accuracy needs separate supervised
validation; synthetic helpers cannot certify it.

## Dashboard and actions

Use actual entity IDs in native Entities card. Enable Mileage timeline explicitly;
wait through 23:55 and a completed local day for genuine prediction comparisons.
Run get_history, get_forecast with 1/7/30/31/365, get_ev_plan with 1/7 and sync_now
using Developer Tools selectors. Invalid/unloaded entry must error. Short EV horizons
must disclose filtered-not-recalculated scope. Switch-on returns promptly, stays on
while busy, returns off after failure/success; user-off does not cancel work.

## Evidence and cleanup

Automated tests cover in-process lifecycle, persistence reconstruction, bounded provider
mocks, domains and many DST/energy cases. They do not replace graphical forms, real
process restart, HAOS packaging, actual provider response semantics or vehicle sessions.
Log failures separately from untested rows. Watch task counts, storage writes and
Recorder churn during idle/refresh; there should be no new UX-triggered network loop.
Remove demo integration entries/helpers/calendar, restore backup or discard VM. Never
reuse artificial mileage history for a real vehicle.
