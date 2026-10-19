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
