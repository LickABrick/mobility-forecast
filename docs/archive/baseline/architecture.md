# Architecture

Each config entry is one vehicle and owns a typed `VehicleCoordinator` in `runtime_data`. No mutable vehicle globals exist.

- `config_flow`: single-screen source selection, options and source reconfiguration.
- `odometer`: source semantics, unit conversion and finite-value validation.
- `history`: recorder executor imports, source overlap normalization, ordered continuity and daily interval aggregation.
- `storage`: version-1 HA Store per entry, atomic delayed writes and unload flush. Corrupt data is not overwritten. Removal deletes only this store.
- `forecasting` / `models`: deterministic ordinary Python domain logic.
- `calendar_manager` / `locations`: bounded native calendar action and conservative location normalization; no event titles persist.
- `routing`: small provider protocol, Waze response adapter, bounded cache and plausible trip chains.
- `sensor`: five coordinator entities with stable entry-based unique IDs and localized names.
- `diagnostics`: privacy-minimal counts, feature status and evaluation.

Live changes debounce recalculation for 60 seconds; periodic refresh is 30 minutes. Chronological live readings append/replace hourly endpoints without whole-history sorting. History import compacts first/last physical readings per UTC hour, retaining three-year coverage independently of report rate; raw database reads are six-hour batches. Schema v1 four-column rows remain compatible; old files are read in full, validated and compacted idempotently, never sliced to the latest N rows.

Calendar work is an entry-owned background task, outside the historical-state lock. A 45-second work-cycle budget covers event retrieval plus routing; three fixed workers process independent daily chains. Identical in-flight legs share a future. Configuration generations reject obsolete results; unload cancels/awaits work. Completion requests a forecast refresh; odometer updates publish immediately without external waits. A failed fresh retrieval clears untrusted stale overlays; a later work-cycle timeout preserves completed days. Fresh agenda retrievals are spaced at least 30 minutes, with pending-work continuations after one minute. Imports execute in the recorder executor and merge against current memory, preserving intervening live updates. Entries own their background import and listeners. Unload cancels pending work, flushes state and shuts down the coordinator.

Forecast computation is inexpensive and bounded by retained readings/365 forecast days. Calendar queries cover at most 30 upcoming days. Waze uses metric units, selects the fastest valid alternative, and never substitutes failed requests with zero distance. Hash-keyed cache identity includes provider/region/preferences/origin/destination.

No recorder database is written. Supported sources are states and semantically suitable state statistics; `sum` is not a mileage value. Reconfiguration preserves entity identity and rejects clearly discontinuous history.

## Entity startup contract

Sensor forwarding precedes asynchronous initialization. The coordinator starts with an initializing forecast containing five null values; sensors explicitly remain available while the forecast is unknown or in error. Unique IDs remain `<entry_id>_<forecast_key>`, device identity remains `<domain>,<entry_id>`. Explicit user-disabled registry entries are respected, never forcibly re-enabled. Initialization and import tasks belong to the config entry; shutdown cancels initialization before other work and never flushes an unloaded empty store over disk. Import failure leaves registered entities and existing history intact.

Recorder planning uses the supported `history.state_changes_during_period` function with ascending `limit=1` and no start-state lookup to find the first retained change for this entity. Detailed six-hour reads start there; statistics remain in 90-day batches. There is no direct database-table query or assumed retention setting. Short raw brackets (up to two hours) supersede statistics, not the global raw min/max extent. Monotonic/speed validation still applies to merged physical states.

## Progressive calendar routing

The calendar pipeline retrieves and validates native `calendar.get_events` responses, normalizes/deduplicates, separates virtual events, applies optional pure containment preprocessing, then checks remaining daily itineraries for unresolved locations/conflicts. Containment compares UTC instants and retains deterministic outermost valid parents; it does not use titles or address equality.

A planning generation retains at most the evaluated 30-day horizon's grouped events in memory (never persisted). Three fixed workers take days chronologically; each day's travel legs are ordered. Completed day plans are committed atomically and request forecast publication. Failed chains publish no partial mileage. The 45-second work-cycle budget and 60-request cap remain. Budget-exhausted/timeout days remain pending; a single cancellable one-minute timer resumes them using cached legs. Failed requests/incomplete itineraries are retried at the regular 30-minute agenda refresh, not in a tight loop. Generations expire at 30 minutes even if pending, fetching current appointments again. Old plans are invalidated after a failed fresh fetch rather than silently reused as trusted overlays.

Options changes reject obsolete task results and clear agenda plans, not history/cache. Shutdown cancels timers and entry-owned work. Same-provider in-flight requests share a shielded future; cancelling a waiter cannot cancel the shared result. Cache keys include provider/region/unit/vehicle and normalized endpoints, stored as hashes only. Failed requests never cache zero. Future-dated/expired cache entries are not reused. Requests and progress counts are aggregate, without event content. Day-specific conflicts remain conservative for overnight and all-day appointments.

## Cache identity, ownership and persistence

The existing v1 SHA-256 key format remains `waze|region|metric|car|canonical-origin|canonical-destination`. The adapter's only selectable route-affecting option is region; realtime=false, car, metric and empty inclusion/exclusion filters remain fixed. Direction is significant. Location identity and Waze query are separate: query strings remain valid geographic inputs, not hashes. Location equality compares identity only, so query spelling cannot cause spurious same-location conflicts.

Canonical address identities casefold and collapse whitespace and comma spacing, retaining numbers, additions, units and postal codes. Decimal coordinates normalize equivalent spellings without float rounding; a minimum five-decimal rendering preserves exact legacy identities, with extra digits retained when present. The original supplied address spelling can probe a safely equivalent legacy hash. Other v1 keys remain readable but cannot be reverse-mapped from their hashes; unavailable old spellings gradually refresh rather than being bulk-deleted. Previously rounded high-precision coordinates are not used as a compatibility fallback because equivalence is unproven.

Cache validation rejects non-dicts, malformed/non-hash keys, nonnumeric/bool values, nonfinite values, nonpositive/future timestamps, nonpositive distinct-endpoint distances, negative durations and expired entries. Expiration pruning precedes oldest-calculation-time capacity eviction. Zero distance exists only as a same-canonical-location shortcut and is not persisted. Valid old numeric schema-v1 entries remain unchanged.

Each work cycle shares one provider across three day workers. At most three owned request tasks exist; consumers await shielded tasks with reference counts. Cancelling the first caller does not cancel another consumer's route. The last consumer cancels/awaits unfinished work, and cycle cleanup explicitly cancels/awaits remaining owned requests. Budgets and deadlines are unchanged. Identical waiting consumers see the same error/budget result rather than dangling futures.

Cycle-finally cleanup schedules HA debounced persistence even after later failures/deadlines or generation cancellation. This does not serialize readings on each Waze call. HA still writes one atomic per-vehicle payload (schema v1), not a separate cache database. A crash before the debounce can lose recent cache entries, never intentionally reset history. Cache storage remains private to each vehicle.

## Reliability processing update (supersedes earlier unresolved-event behavior)

Strict response-level validation is retained. Individual malformed rows are isolated and counted by normalization; canceled rows are excluded, not routed. Non-routable events are then excluded before containment/physical conflict checks. An all-locationless calendar succeeds with no plans and no Waze calls; historical forecasts remain unchanged.

Plan.retryable distinguishes transient route_unavailable/route_timeout from terminal conflicting_appointments, impossible_itinerary, unsupported_all_day and unsupported_overnight. A transient day stays pending with an incomplete zero-overlay plan, cached successful legs retained. At most three transient attempts per day per generation are allowed, with 60 seconds then 120 seconds between attempts. Budget/deadline deferral does not consume transient attempts. Retry state resets on new agenda retrieval/options generation; exhausted days can be tried at the next regular 30-minute refresh. Deferred work and retry timers remain single, bounded, entry-owned callbacks. Only complete daily plans affect predicted mileage.

Calendar publication is separate from odometer debounce: first completed day requests refresh promptly, subsequent completions coalesce on one two-second timer, and final cycle status requests refresh after cancelling the pending timer. Native coordinator debouncing still serializes actual updates. Publication tasks/timers are cancelled on shutdown; generation checks reject obsolete timer callbacks. Waze work never waits under the history lock. Long cycles publish intermediate batches, not just a final monthly result.

## Calendar synchronization and comparison pipeline

Active `plans` and committed hashed `day_fingerprints` are separate from candidate
calendar groups/fingerprints. Retrieval does not clear active plans. A successful
response removes deleted dates; changed physical days are routed independently and
committed as whole-day results. Retryable candidate failures do not replace a valid
active plan. Terminal physical conflicts invalidate the overlay. The existing
three-worker, 60-request, 45-second cycle limits and retry/cache ownership remain.
Fingerprints exclude titles and normalize UTC instants and canonical locations.

Odometer aggregation is memoized by timezone plus the complete immutable reading
sequence, so revised/backfilled samples invalidate it. Rolling forecasts still
calculate against the clock. `generated_at` is no longer copied to every sensor;
the read action exposes calculation time. Status/progress attributes still update.
Comparison functions are pure; schema-v1 vehicle storage remains atomic and keeps
four-column readings and route caches. Snapshots use individual structured schema-1
records inside that existing store, not a destructive store-version migration.

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

## Reliability correction (2026-10-20)

Python distribution discovery is explicitly restricted to `custom_components` and its namespace packages. Repository assets are not Python packages. CI now builds and inspects a wheel, in addition to editable installation and `pip check`. Pillow is explicitly test-only; offline brand tooling remains outside runtime requirements.
