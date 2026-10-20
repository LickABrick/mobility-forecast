# Troubleshooting

- **Mostly parked vehicles:** confirmed zero days count toward driving probability; recurring weekend or weekly travel is not discarded as an outlier. Missing telemetry is not a confirmed zero. Compare several weeks, not one unexpected journey.
- **Slow routing:** historical forecasts publish independently. Agenda processing has a 45-second work-cycle deadline; pending days resume after one minute while failed requests retry at the regular refresh. routing_unavailable means historical fallback, not zero-distance journeys.
- **Odometer selector:** displays distance-class sensors or sensors in km/mi. Incomplete device-class metadata is supported through the unit fallback. Final validation still rejects trip/range counters.
- **Learning / unknown predictions:** wait for seven adequately bracketed days or verify recorder has retained this odometer. No updates is not evidence of a parked car.
- **Source unavailable:** history remains stored. Check original integration, unit and numeric value. After seven days without valid measurements predictions become unknown instead of indefinitely fresh-looking values.
- **Source rejected:** range/trip sensors are unsuitable. Use lifetime cumulative mileage, preferably a distance sensor with total state class.
- **Counter decrease / replacement:** data is rejected to avoid negative trips. Restore a continuous source. Start a new vehicle entry only if deliberately discarding the model is appropriate.
- **No calendar contribution:** verify calendars, routing opt-in, Waze action and region. Generic names need a known location/zone. Online, all-day, crossing-midnight or impossible overlapping itineraries may not yield routes.
- **Routing unavailable:** historical forecasts remain valid. Provider errors are not zero-distance journeys. Requests retry on later refresh and usable cached routes remain until expiration.
- **Storage repair:** unreadable state is preserved, not overwritten. Restore a backup or remove/re-add the vehicle to start fresh. There is no safe automatic interpretation of arbitrary corrupt files.

For bug reports provide integration version, HA version, sanitized downloaded diagnostics and reproduction steps. Do not attach private calendar content, addresses, coordinates, storage files or authentication details publicly.

## Five sensors missing from States

1. Open Settings → Devices & services → Mobility Forecast. Check whether the entry is loaded, disabled, retrying or **Failed to set up**.
2. Open the vehicle device → Entities. Enable any user-disabled sensors. Search the actual entity IDs in Developer Tools → States (names/IDs may have been renamed).
3. Registered enabled entities should have a state even with no history: `unknown`, not absent. Inspect `forecast_status`, `history_days`, `history_import_status`, `calendar_status`.
4. Check Settings → System → Logs for `custom_components.mobility_forecast`, platform `sensor`, config entry setup and entity-registration errors. Enable integration debug logging temporarily if needed, then disable it.
5. If still missing, provide HA Core version, integration version/installed commit, entry load status, entity registry disabled status and startup traceback. Redact locations, vehicle identifiers and calendar details. Do not delete the entry/history to troubleshoot.

The production missing-entity report was not reproduced in the in-process HA tests. Startup was hardened against initialization blocking registration, but no specific cause in that installation has been confirmed.

`history_import_status`: pending/importing/complete/failed/incompatible_source. `forecast_status`: initializing/learning/provisional/ready/source_unavailable/source_incompatible/error. Resetting counters raise Repairs; select a lifetime vehicle odometer via Reconfigure. Calendar `routing_unavailable` is historical fallback, not failure of the five sensors.

## Calendar progress and failures

| calendar_status | Meaning |
|---|---|
| disabled | Calendar routing is not enabled |
| refreshing | Retrieval or initial work is running; no completed overlay yet |
| ready | All required days in the fetched horizon completed (including an empty agenda) |
| partial | Some valid days completed; other days are pending or incomplete |
| incomplete | Itineraries cannot be completed, e.g. unresolved locations or conflicts |
| calendar_unavailable | Calendar retrieval/response validation failed; old agenda overlays are untrusted |
| routing_unavailable | No valid completed days and route service/request failed |
| routing_timeout | Work-cycle deadline expired before any valid day completed |

`calendar_last_failure` uses safe categories such as calendar_fetch, calendar_normalization, route_planning, provider_unavailable, route_request, request_budget, refresh_timeout, missing_location and conflicting_appointments. Logs contain only stage, exception class and aggregate counts, never exception messages or calendar content. `calendar_last_success` is the last fully successful refresh, not a claim that pending results are fresh. Complete-day counts refer to route plans; incomplete/pending days use historical mileage. Request counts are cumulative across work cycles for the current agenda generation, including failed requests.

150 appointments alone do not prove a cause for routing_unavailable. Check stage/progress first. Waze unavailability, invalid responses, conflicting calendars and the old global deadline can all explain failures. No runtime cause in the reported installation has been established. Allow several continuation cycles for a large unique-location calendar. Near-term plans should appear before the whole month completes. If a trip is missing, check unresolved locations and overlaps before enabling nested filtering.

## Cache efficiency diagnostics

Counters are **per last processing cycle**, not lifetime or cumulative agenda totals. `calendar_requests` remains the separate cumulative agenda-generation counter. Diagnostics `route_cache_statistics` contains:

- route_lookups: consumer calls, including same-location shortcuts.
- route_cache_hits: valid cached lookups performed by the shared calculation (not each waiter).
- route_cache_misses: shared calculations without a valid cache entry, including provider-unavailable/budget-deferred attempts; not synonymous with Waze calls.
- route_cache_expired: expired entries removed by pruning, including initial cycle cleanup, not just requested entries.
- route_requests_deduplicated: additional consumers joining an outstanding calculation.
- waze_requests: actual service invocations, including failed/cancelled calls.
- waze_failures: completed service attempts with exceptions or invalid/no routes; cycle cancellation is not counted as a provider failure.
- route_cache_evictions: capacity removals only, not expired/invalid cleanup.
- route_cache_entries: retained entries at the cycle end (a gauge).

Same-location shortcuts count neither hits nor misses. Successful warm-cache cycles have zero Waze calls; cache misses during an outage never become fabricated zero routes. Debug summaries contain only counts. Diagnostics expose no endpoint strings, hashes, titles or descriptions. Cache hashes hide plaintext but are not encryption against guessed-address attacks; protect HA backups.

## Location and retry interpretation (current behavior)

`missing_location` is no longer emitted for intentionally excluded events. Check:
- calendar_events_count: retrieved raw rows (including malformed/canceled/duplicates).
- calendar_events_invalid_skipped: malformed rows; other valid events still process.
- calendar_events_routable: normalized physical candidates before nesting.
- calendar_events_without_location: normalized nonvirtual unresolved/locationless events skipped.
- calendar_events_virtual_skipped: normalized virtual events skipped.
- calendar_nested_ignored: physical children removed by the optional containment rule.

These counts need not sum to raw rows because normalization also deduplicates/culls canceled/out-of-horizon events. `ready` means all required known physical itineraries completed, not that the calendar describes every real trip. `partial` means completed days plus pending/incomplete days. `incomplete` identifies terminal planning failures when no complete overlay exists. `routing_unavailable` covers transient Waze failures without a usable completed day; retries may still be pending. `routing_timeout` indicates cycle-deadline deferral without a completed day. `calendar_unavailable` means response/service-level failure, not one malformed event.

Current failure categories: route_unavailable, route_timeout (retryable); impossible_itinerary, conflicting_appointments, unsupported_all_day, unsupported_overnight (terminal this generation); request_budget/refresh_timeout (deferred); calendar_fetch/calendar_normalization/route_planning (pipeline failures). `calendar_retry_exhausted` counts days reaching three transient failures. A normal fresh agenda refresh can retry again. `calendar_last_failure` records a recent reason in an incomplete generation and clears on full success; it is not an individual-event diagnosis. Historical mileage remains usable during routing errors. Never enable nested filtering merely to hide genuinely conflicting physical appointments.

## Stale agendas and empty comparison charts

Calendar retrieval failures retain a last verified plan for at most two hours,
reporting `stale`. After that the historical baseline applies. This deliberately
allows a real downward change rather than claiming an old appointment remains
verified forever. Authoritative removal invalidates canceled days immediately.
Changed itineraries can temporarily retain their last good plan while a candidate
retries, also subject to the two-hour verification limit. Routes are reconsidered
after seven days even when the itinerary remains identical. Plans/fingerprints
are runtime-only: reload rebuilds them using the persisted route cache.

Empty comparison history immediately after installation is expected: wait for
a 23:55 capture and a completed target day with adequate odometer coverage.
Legacy first-calculation snapshots are not verified pre-day predictions. Enable
the timeline entity and use its actual ID in the optional ApexCharts examples.
The chart timezone should match HA. Never convert missing distances to zero.

## Optional EV charging forecast

See [EV setup, assumptions, provider limits and native dashboard](ev.md). EV is
disabled by default and never controls the vehicle or charger. Existing mileage
entities, history and calendar synchronization remain independent.
