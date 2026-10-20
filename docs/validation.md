# Release hardening validation

## Tested environment

Primary: **Home Assistant Core 2026.10.2 / Python 3.14.2**, isolated uv-managed `.venv314`, authoritative PyPI source. pytest-homeassistant-custom-component 0.13.373. The original 43-test baseline also passed under this environment before changes; original implementation previously ran under HA 2026.2.3/Python 3.13.5. Minimum supported HA is now 2026.10.2.

The previous package-index diagnosis was incorrect: Python 3.13 filtered out HA releases requiring >=3.14.2. No custom package index was configured. System Python was not replaced.

## Checks

- Full pytest suite after reliability remediation: **87 passing**.
- Ruff lint and formatting: passing.
- Mypy: passing, expanded to seven model/forecast/odometer/history/location/calendar/routing modules. HA coordinator/flow adapters are exercised by runtime tests but not fully statically typed.
- Offline metadata and English/Dutch translation-key parity: passing.
- Actual upstream Hassfest Docker validator: **1 integration, 0 invalid**. Image digest `sha256:2dce3c5423a600e7965e5a3d5a95e0707e8452fb001ab2b5d0602099bbecba92`. Its initial missing-recorder-dependency finding was fixed with optional after_dependencies.
- HACS validator attempted using `ghcr.io/hacs/action:main`: **blocked**, exact error `No GitHub token found, use env GITHUB_TOKEN to set this.` No token was requested/generated and no publication was attempted. Offline layout/metadata checks pass, but full HACS acceptance is unverified.

In-process HA tests exercise native config/duplicate/error flows, known-location forms, calendar options, source reconfiguration, setup without calendars, five native sensors, multiple independent vehicles, reload/persistence/removal, v1 payload compatibility and corrupt-state preservation. Recorder/statistics import has adapter tests. Waze tests use HA 2026.10's actual service registration/schema/handler and coordinator response conversion, mocking only external pywaze calculations. All supported regions and failure/recovery are exercised. This is **not** a live Waze or production browser/server test.

## Resolved release-blocking defects

- Initial history import incorrectly used current state as the watermark and imported only one day.
- Mixed-zone DST arithmetic changed allocated interval distances.
- Statistics-derived days could be treated as precise weekday evidence.
- Overlapping statistics and raw telemetry could introduce artificial steps.
- Late high readings could evict already accepted later history.
- Rolling forecasts could include already-driven kilometers again.
- Nested overlapping appointments could produce impossible trips; overnight dates were incompletely marked.
- Persisted malformed route cache or corrupt storage could break updates or risk overwrite.
- High-frequency forecast updates unnecessarily repeated calendar queries and unchanged storage writes.
- Technical JSON known-location editor replaced with native add/edit/remove forms.

Storage remains **schema version 1**, retaining original four-column readings and known-location mapping. Added optional state is defaulted; no destructive migration or silent reset occurs. Invalid persisted samples stop writes and surface a repair.

## Gap classification

### Remaining release-blocking defects / data-integrity risks

No critical defect is currently demonstrated by the local suite. This does not certify the original exhaustive matrix or production behavior. HACS token-dependent validation remains an uncompleted distribution gate, not a demonstrated runtime defect.

### Acceptable beta limitations

- No live Waze/network or graphical browser smoke test. No full production server restart test: unload/reload plus Store reconstruction simulate the relevant lifecycle/persistence boundaries.
- Thirty-minute calendar refresh; no calendar push subscriptions. Local midnight refresh is scheduled separately.
- Source registry renames resolve on reload. Discontinuous replacements/resets are rejected rather than rebased; user must restore a continuous source or deliberately start a fresh vehicle.
- All-day/overnight/impossible itineraries conservatively fall back to history. Missing location events can make a daily itinerary incomplete. No vehicle assignment is inferred.
- Daily interval allocation and rolling partial-day allocation are approximate. Internal ranges are indicative, not calibrated probabilities.
- No pre-v1 storage migration exists because no pre-v1 schema is supported; existing v1 payloads remain compatible.
- Address recognition requires street number/locality separator or explicit coordinates/HA zones. Generic venue names need native known-location forms.

### Optional future enhancements

Default-disabled diagnostic entities, separate actual/remaining-distance entities, calibrated uncertainty and learned calendar overlap. These are not required to use the five core sensors.

## Reliability remediation follow-up

Added deterministic intermittent/weekend/weekly/low-mileage tests, synthetic rolling-origin old/new backtests (MAE, signed bias and aggregate 7/30-day errors), frequency-independent retention and three-year coverage tests, a real recorder-adapter-to-HA-sensor pipeline with reload/persistence, background-routing coalescing/cancellation/config-generation tests and a whole-refresh deadline regression. Full results and measured compaction memory/time are in [performance.md](performance.md).

Historical retention no longer slices to the latest 50,000 samples. Schema v1 remains unchanged: original files are validated in full then compacted to first/last observations per UTC hour. This is an idempotent representation migration, preserving measured cumulative endpoints; corrupt files remain write-protected. Compaction can conservatively reduce precise daily evidence for fractional-offset timezone midnights, never increase it.

External calendar/routing work is outside the history lock, with three fixed day workers, in-flight leg deduplication, 60-request cap and 45-second whole-refresh timeout. Failed overlays are removed and status distinguishes routing_unavailable; historical forecasting remains usable. Default selector uses supported OR filters: distance device class or km/mi units, preserving nonstandard metadata sources.

CI remains Python 3.14 with pinned HA 2026.10.2, tests, Ruff, expanded Mypy, translation validation, Hassfest and HACS jobs, read-only contents permission. No checks were disabled. Local Hassfest re-run passed; local HACS was attempted again and still requires a GitHub token. Configured GitHub Actions must supply its ordinary token; no credentials were printed or committed. No public repository metadata was changed.

Remaining verification limits: no real vehicle telemetry, browser interaction, live Waze network or production restart. Synthetic repeated-week performance is not a real-world accuracy guarantee. The entire original exhaustive test matrix is not claimed covered: several concurrency/failure combinations are tested through shared primitives rather than every Cartesian combination. Native selector UI cannot rank likely odometers within the filtered set. Recorder import remains time-window bounded, not SQL-row streamed; extreme subsecond reporting may require further batching work.

## Beta assessment

Suitable for **supervised real-world beta testing** on HA 2026.10.2 with a Home Assistant backup and side-by-side checking against actual mileage. Not a claim of exhaustive production certification or HACS catalog approval. No push or release publication has occurred.

## Final visibility/history follow-up

Python 3.14.2 / HA 2026.10.2: **110 tests passed**, Ruff lint/format passed, Mypy seven-module scope passed, offline metadata/translation validation and diff whitespace checks passed. Upstream Docker Hassfest: one integration, zero invalid. HACS Docker attempted: blocked by `No GitHub token found`; no local HACS pass claimed. No hosted Actions run was triggered and no commits were pushed. Repository topics/description were not modified. After pushing, run Quality manually (new workflow_dispatch) to verify current remote metadata with HACS. Checkout 7.0.1 and setup-python 7.0.0 were verified via their upstream latest-release APIs; read-only contents permission retained.

Missing entities could not be reproduced in the HA fixture. New setup tests assert all five enabled registry entries and corresponding unknown state-machine values with no source, unavailable/invalid source or a single reading. Blocked storage initialization no longer delays sensor forwarding. Failed imports preserve entity registration. User-disabled entities retain identities/disabled state through reload. Existing full-pipeline numeric import, multi-vehicle, cache/deadline/unload/storage tests remain passing. This is in-process verification, not confirmation of the user's production installation.

Reset detection operates on raw values before monotonic rejection, including import batches; two distinct UTC decrease dates raise a repair and withhold predictions without clearing valid history. Known walking/running/daily/trip sources are rejected on setup. Metadata is not definitive for ambiguous names. Evening cadence provides half-weight weekday evidence, not exact historical totals. Supported row-limited Recorder boundary discovery avoids empty years; gap-aware overlap retains statistics inside long raw gaps.

Remaining limitations: no production access, graphical UI test, live Waze or physical vehicle telemetry. A full process restart and interrupted disk write were not executed against a production HA server. Fixture reload/persistence is not equivalent to that test. The exhaustive requested matrix is not fully covered (e.g. arbitrary holiday timing, every journey cadence and all reset/reconfigure combinations). Reset heuristics can misclassify repeated telemetry glitches; late-arriving old reports are ignored for live reset detection. The heuristic evening attribution assumes driving finishes before the report. Six-hour recorder batches remain potentially large for subsecond reporting. Supervised beta remains appropriate with backups, not unconditional production certification.

Final independent source inspection found that Recorder windows exclude their lower timestamp bound. The oldest retained raw observation is now explicitly imported as an anchor before window queries; regression checks assert its preservation. This adds no extra query. The boundary API finds the earliest value *change*, not every attribute-only update, so older unchanged/attribute-only brackets may still be conservatively omitted. No claim is made that it discovers every retained database row.

## Scalable routing and nesting follow-up

Local HA 2026.10.2 / Python 3.14.2: 137 tests pass, including 150/300-appointment progressive service tests, deadline retention, bounded 60-call cycles/three workers, cache continuation, nested input-order permutations, multi-level nesting, equal/partial/adjacent/all-day/overnight/unresolved containers, UTC/DST containment, virtual-event separation, native option persistence/toggle, unavailable provider, privacy-safe errors, inflight waiter cancellation and region-separated caches. Existing historical, entity visibility, storage, lifecycle and conservative overlay tests remain passing. No storage schema or entity identity change.

Reported real-instance root cause remains unconfirmed. Verified failure paths: fetch exceptions, malformed responses, provider absence, request errors and refresh deadlines. The previous deadline discarded completed work; progressive day commits correct that behavior. Tests use mocked external service responses, not live Waze. Cross-calendar normalization operates on the combined response; no calendar-title/address inference is used. Full HA process restart and real browser verification remain manual, not inferred from option fixture tests.

Final checks: pytest 137 passed; Ruff lint/format, seven-module Mypy, metadata/translation validator and git diff --check passed. Docker Hassfest passed (one integration, zero invalid). Docker HACS attempted and blocked by missing GITHUB_TOKEN; no hosted run or live Waze verification claimed. Additional 150/300 nested calendars complete with 60 calls and 120/270 ignored tickets, respectively. Strict mode would reject those overlapping days before making calls. Remaining limits include whole-generation 30-minute freshness, conservative all-day/overnight handling and potential repeated leg requests after cache eviction in very large unique-location agendas; 512-entry bound is retained.

## Intelligent route caching follow-up

Baseline 6170e18 inspected; existing persistent caching, direction/region separation and deduplication were retained, not recreated as new features. Fixed unsafe persisted value validation (including non-dict and string-type failures), expiry-before-capacity cleanup, cycle-finally debounce persistence, location equality/query separation, exact Decimal coordinate precision and first-consumer cancellation propagation. Cache metrics are explicitly last-cycle scope. Existing schema-v1 valid entries and vehicle history are preserved; unsupported/expired cache data is rejected rather than treated as mileage.

Tests cover cache corruption, persistence/reconstruction through HA Store, expiry with clock advancement, legacy formatting-key reuse, different directed route values, five-location 150/300 calendars, warm second cycles, safe normalization/no fuzzy merging, alias/region changes, provider outage with valid cache, reference-counted cancellation and failed-request recovery. Existing progressive timeout/unload/config-generation, nested filtering, multiple vehicles and historical-only sensor tests remain included. Real full-process restart, browser UX and live Waze were not executed; fixture reconstruction is not production restart certification.

Final local results: **163 pytest tests passed** on HA 2026.10.2/Python 3.14.2; Ruff lint and format, Mypy (seven configured modules), metadata/translation validation and git diff --check passed. Upstream Docker Hassfest passed: one integration, zero invalid. HACS Docker was attempted and stopped with missing GITHUB_TOKEN; local HACS and hosted Actions success are not claimed. No new user-facing options, dependencies, storage migration or translations were needed; existing English/Dutch parity remains validated. Nothing pushed or published.

## Calendar reliability final hardening

Root cause of missing_location confirmed in code: unresolved appointments entered physical daily validation, which invalidated the whole day. Non-routable filtering now runs first, with separate virtual/locationless counters. Individual malformed rows no longer invalidate the response; response containers remain strict. Transient route errors stay pending for up to three attempts, 60/120-second backoff, while terminal schedules are not retried. Successful legs persist and partial mileage never overlays history. Impossible travel time is a schedule error, not a Waze request error. Calendar publications coalesce (first/last plus two-second batches) instead of per-day refresh requests.

Acceptance tests execute actual in-process HA calendar service → normalization/filtering → Waze adapter/cache → retry → coordinator → five sensors, with persisted reload identity/cache checks, for 0/1/30/150/300 rows. Synthetic external Waze responses only; no real calendar/production instance was accessed. Prior tests retain coverage for unique routes, options invalidation, cancellation, independent vehicles, storage corruption, historical-only forecasts and rolling/annual values. Not every requested scheduling/cancellation combination is exhaustively exercised; production process restart/browser/live-network testing remains manual.

Final local checks: **189 tests passed** on HA 2026.10.2/Python 3.14.2; Ruff lint/format passed, Mypy seven-module scope passed, metadata/English-Dutch translation parity passed, git diff --check passed. Docker Hassfest passed (one integration, zero invalid). Docker HACS attempted: blocked by missing GITHUB_TOKEN; no HACS or hosted Actions pass claimed. Final audit additionally bounded publication task creation when a prior publication is still active and reset retry-exhaustion metadata on fresh agendas. No dependencies/settings/schema/unique-ID changes, pushes or releases.

## Stable synchronization and comparison acceptance

Local HA 2026.10.2/Python 3.14.2 suite includes delayed 67 km refresh stability,
24-hour unchanged itinerary reuse, canonical spelling/title reuse, changed location,
authoritative cancellation, two-hour stale outage fallback, pre-day immutability,
legacy migration, DST-adjacent 23:55 captures, observed-only metric eligibility,
response-to-chart alignment and persistent snapshot reload. Existing 150/300-event,
retry, nested, malformed, source and multi-vehicle tests remain enabled.

Limitations: this is synthetic/in-process HA evidence. No live calendar/Waze,
production process restart, actual Lovelace browser rendering, comprehensive new
23/25-hour callback scheduling matrix or matched before/after Recorder/storage
benchmark was executed. The chart examples match tested response fields, but are
not certified through a graphical browser. HACS Docker is blocked without a GitHub
token. Hassfest Docker passes including new services/translations.

## Initial EV extension validation

213 tests pass on HA 2026.10.2 / Python 3.14.2. Ruff lint/format, configured
seven-module Mypy, metadata/EN-NL parity, diff checks and Hassfest Docker pass.
HACS remains token-blocked. New deterministic coverage includes unit-aware energy,
SoC invalid values, reserve ranges, target exceptions and enforced limits,
chronological unreachability, optional setup consent, strict provider parsing,
30/150/300 lookup bounds, native EV entities/action and unload. This does not
constitute the full requested 90-scenario matrix.

PDOK OpenAPI and NDW OpenAPI plus a real small-area NDW response were retrieved.
NDW power units disagree between specification and observed response; adapter
rejects ambiguous powers. No real vehicle/session, end-to-end live PDOK address
resolution, public-charging success or graphical dashboard was certified. See
[EV limitations](ev.md) before supervised testing.

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

## Manual sync and brand validation

The manual-sync/branding change passes 228 tests on the Python 3.14 / HA 2026.10.2
test environment, Ruff lint/format, configured seven-module Mypy, metadata and
translation parity, and diff checks. Hassfest Docker: one integration, zero
invalid. HACS Docker cannot proceed without `GITHUB_TOKEN`; offline HACS metadata
validation passed. No real HA process restart or GitHub browser rendering was
performed. SVG links resolve locally; PNGs were generated and visually inspected,
and automated checks cover dimensions, transparency, local SVG structure and size.

Manual-sync coverage includes entry setup/reload, HA switch services, user-off
while busy, coalescing, failure sanitization, timeout, independent controllers,
unload interruption, forced agenda verification, odometer ingestion and EV
orchestration (mocked EV boundary). Existing calendar/provider/lifecycle tests
remain green; this does not establish live external-provider availability.
