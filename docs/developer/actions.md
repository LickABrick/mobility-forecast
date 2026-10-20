# Native action contracts

All actions target one loaded vehicle config-entry ID; use the native selector in
Developer Tools → Actions. Invalid/unloaded entries raise an action error. Read-only
responses are snapshots and do not fetch providers, refresh calendars or persist data.
Returned mappings/lists are new objects; callers cannot modify coordinator state.

## get_forecast

`days` is 1–365, default **30 local forecast dates**, starting with today's full-day
record. Results are capped by available model dates; no missing future rows are
fabricated. Fields remain `entry_id`, `calculated_at`, `forecast` with `date`, local
midnight `timestamp` (including DST offset), `predicted_km`, `low_km`, `high_km`.
Rows additionally expose `data_quality`. Before sufficient history, verified calendar-only
rows have null baseline uncertainty (`low_km`/`high_km`); unknown dates have null mileage.
Consumers must not coerce null to zero. See [calendar-only rules](../sync-diagnostics.md#calendar-only-estimates).

**Compatibility correction:** older actions ignored days and returned up to 31 rows.
Explicit requests now work and default actions return 30. Mileage timeline retains
its 31-row display independently. Automations requiring 31 must request `days: 31`.
Daily rows differ from rolling sensor totals, which allocate partial endpoint days.

```yaml
action: mobility_forecast.get_forecast
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
  days: 7
response_variable: forecast
```

## get_history

`days` is 1–365, default 30 completed local dates. Missing observations/predictions
are null, not zero. `accuracy` evaluates strict observed/predicted pairs over 7/30/90
days independent of display filtering. Difference is actual minus predicted. No
startup backfill invents genuine pre-day prediction snapshots.

## get_ev_plan

`horizon_days` is 1–7, default 7. Internal assessment remains seven local dates.
Shorter responses identify `filtered_not_recalculated` and withhold recommendation,
alternative and shortfall rather than claim independent optimization. Disabled EV
returns a disabled schema-1 response. No providers or controls are called.

## sync_now

This is the only mutating maintenance action: it waits for bounded refresh work,
with a 120-second manual deadline and sanitized errors on failure. The switch queues
work without waiting and user-off does not cancel it. Success is cycle completion,
not proof every external route or charger was available.
