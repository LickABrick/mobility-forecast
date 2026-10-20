# Sync and forecast diagnostics

Each vehicle has four enabled diagnostic sensors on its existing device. They observe
runtime state without polling or querying providers. Entity IDs depend on your chosen
vehicle name; use the device page to find them.

## Manual Sync lifecycle

Switch-on acknowledges immediately and stays on during the job. User-off does not
cancel it. A genuinely fast job can finish quickly; there is no artificial delay.
The shared deadline is 120 seconds, including coalesced follow-ups. Repeated requests
join one owned worker and set at most one pending follow-up at a time; requests during
a follow-up are handled too, within the same deadline.

Scope: wait for initialization and any initial history import, ingest current odometer
state, join automatic calendar work, request a fresh agenda and process one bounded
routing batch, publish mileage, then reconcile optional EV computation. It does not
reimport years of Recorder history, wait for future retry timers or exhaust public
charger discovery. Existing three-worker/60-request/45-second calendar budgets remain.
Automatic work can continue separately after a partial attempt.

**Sync status** primary state is `idle` or `syncing`. Attributes:

- `phase`: initializing, history, calendar, routing, forecast, ev, finalizing; null at idle.
- `last_result`: never_run, success, partial, error, interrupted.
- `last_requested_at`, `last_started_at`, `last_finished_at`: UTC timestamps.
- `duration_seconds`: computed once at completion, not a ticking counter.
- `last_error_code`: sanitized category, never private provider exception text.
- `pending_followup`: one coalesced request is waiting.

Results mean:

- **success**: requested scope completed, including fresh calendar verification with no
  known incomplete/pending routes when enabled. EV `insufficient_data` is a valid
  computation, not a worker failure. Learning mileage can coexist with successful sync.
- **partial**: bounded attempt ended but routing is incomplete/deferred or EV lookups
  remain deferred. It does not mean every configured appointment was processed.
- **error**: source, initialization/history, calendar retrieval, routing/EV computation
  failed, or deadline expired (`sync_timeout`). Fix the category, not raw exception text.
- **interrupted**: unload/shutdown canceled the job; never counted as success.

The nonblocking switch queues work. The `mobility_forecast.sync_now` action waits and
raises a sanitized Home Assistant error for **partial, error or interrupted** outcomes.
Use the switch for interactive progress, or catch action errors in automations.

## Last successful sync

A timestamp sensor, initially unknown. Only fully successful **manual** jobs advance
it. Partial/error attempts do not erase an earlier success. One optional timestamp is
stored in the existing per-vehicle version-1 store, with its normal write debounce and
unload flush. No phase transitions, raw agendas or provider payloads are persisted.
After restart activity is idle and last_result is never_run until another attempt;
the restored timestamp remains available. A crash before the delayed write may lose
the newest timestamp. Corrupt storage is never overwritten to save diagnostics.

## Forecast status

- `initializing`: loading storage/history.
- `learning`: fewer than seven adequately covered completed days and no eligible plan.
- `calendar_only`: verified planned travel is available without a historical baseline.
- `provisional` / `ready`: normal history model with weaker/stronger evidence.
- `source_unavailable` / `source_incompatible`: fix odometer availability/semantics.
- `error`: initialization/model error.

Attributes include `reason`, `history_import_status`, `usable_history_days`,
`required_history_days`, `data_quality`, `calendar_contribution_available`. These are
bounded metadata, not history arrays. Source-error status takes precedence over calendar
availability; calendar availability is not proof of a healthy odometer.

## Calendar status

`disabled` means no calendars or routing off. Selecting calendars alone is insufficient;
Waze Travel Time must provide routing. `refreshing`, `partial`, `incomplete` distinguish
active/deferred/unroutable work. `ready` means the current pipeline completed, not that
there were appointments. `cached`, `provisional`, `stale` explain retained data;
`calendar_unavailable`, `routing_unavailable`, `routing_timeout` explain failures.

Attributes include selected calendar count, fetch attempt/success times, retrieved,
routable, locationless, virtual and invalid event counts, nested ignored count,
complete/incomplete/pending days, route cache hits, Waze requests/failures, failure code
and next retry time where known. Counts refer to the latest fetched agenda/current
routing batch, not lifetime totals. Retrieved rows are counted before deduplication;
routable rows are normalized physical appointments before nested filtering. Ready with
zero retrieved events is a successful fetch, not evidence of zero personal driving.
No event titles, calendar names, locations or coordinates are included.

## Calendar-only estimates

Without seven usable days, only explicit **complete, freshly verified** daily plans
with known nonnegative distances and matching routing configuration qualify. The
existing two-hour freshness applies. Provisional/stale retained plans and changed,
canceled, partial or incompatible plans do not qualify. The model receives a separate
verified-plan input, so an arbitrary cached Plan cannot qualify by itself.

Today/tomorrow and individual daily action/Timeline rows may show the known planned
component. It is **not a statistically learned full-day total**: personal trips may
be absent from calendars. Missing dates are null, never zero. An explicitly routed
0 km is different from an unknown day. Baseline and low/high uncertainty are null;
`data_quality: calendar_only` identifies supported rows. Seven-day, thirty-day and
annual sensors remain unknown. Daily response fields are retained, with additive
`data_quality`; consumers must handle null predicted/bound values.

At seven useful days the unchanged history-based model takes over. Calendar-only
values never create historical accuracy snapshots or fabricate past predictions.
EV stays `insufficient_data` for insufficient/calendar-only mileage, with unknown
energy demand; missing distance is not treated as zero or “no charge needed”.
