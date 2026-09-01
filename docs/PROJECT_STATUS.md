# Project status

Last updated: 2026-09-01 14:32 CEST

## Current phase

Phase 1 and post-phase checkpoints P1–P5 are complete. Work is at the isolated
real Home Assistant lifecycle/entity test handoff.

## Completed

- C0 established the local repository, safety/privacy governance, Apache-2.0 intent, Conventional Commits and deterministic checkpoint tooling.
- C1 defined the V1 outcome, architecture boundaries and ADRs 0001–0005.
- C2 added dependency-free, frozen and typed domain values for normalized source events, coordinates/resolved locations, directional successful routes, passive vehicle observations, degraded trips, shared quality states and uncertainty-aware daily forecasts.
- C2 made privacy-bearing event text and coordinates absent from object representations, rejects naive/reversed event time ranges and invalid numeric measurements, and prevents a failed route from being represented as a zero-valued successful route.
- C2 established Python/package metadata, Ruff and Pyright policy, a standard-library `unittest` foundation and checkpoint execution of the test suite.
- C3 added an immutable, explicit event-filter policy with case-insensitive include/exclude terms matched only against summary and description, plus tested handling for normalized online events, all-day events and missing physical locations.
- C3 uses one stable primary exclusion reason in this order: exclude term, disallowed online, disallowed all-day, required location missing, include mismatch. An explicitly allowed online event does not require a physical location.
- C3 added aggregate-only previews containing total/included/excluded counts and stable reason counts; previews retain no source event, identifier, event text or location text.
- C4 added separate immutable start and end location policies and a pure resolver that never exposes a refresh, service or provider boundary.
- C4 requires all passive-vehicle gates as domain inputs: maximum sample age, maximum accuracy radius and maximum trip horizon. Numeric defaults are intentionally absent, limits are inclusive, and missing/future timestamps, stale samples, unknown/excessive accuracy and out-of-horizon trips have stable privacy-safe reasons.
- C4 accepts event- and zone-derived destinations independently, never accepts vehicle position as a destination, marks configured fallbacks `partial`, and returns explicit `unavailable` results when no allowed fallback exists.
- C5 added asynchronous typed route-provider and cache protocols, provider-neutral requests/options, privacy-safe failures, and deterministic in-memory fakes with exact expected requests and no network path.
- C5 makes route direction, options, departure time and a stable non-secret provider/config namespace part of a profile-keyed HMAC-SHA-256 cache key without retaining raw endpoint identifiers or coordinates. Required fresh/stale age limits have no defaults.
- C5 uses inclusive cache boundaries: fresh hits skip the provider, stale hits attempt refresh and fall back with `stale` quality plus the typed refresh failure, expired entries are not returned, and successful refreshes replace cache entries. Provider/cache direction mismatches are rejected.
- C6 added pure typed itinerary candidates, chronological deduplicated stops, directional planned legs and immutable plan revisions. Explicit adapter-normalized deduplication keys avoid matching on private event text or locations; conflicting duplicate claims fail rather than silently dropping data.
- C6 chains the initial origin through each known stop destination, retains typed route failures as partial legs, breaks the chain explicitly after an unknown destination, and propagates unavailable/partial/stale quality without fabricating zero distance.
- C6 added an append-only revision-history function that rejects duplicate revision identifiers and non-increasing creation times while preserving earlier revision objects unchanged.
- C7 added explicit passive-odometer acceptance policy for missing, future and stale samples; inclusive sample-age limits and a maximum daily-distance guard have no domain defaults.
- C7 opens pending days only from a complete positive routed plan that existed at opening time, snapshots that immutable revision identifier and distance, and rejects stale/non-newer end samples, odometer rollback and excessive daily movement at closure.
- C7 added a robust distance baseline that rejects duplicate or nonhistorical training actuals, excludes ratios outside explicit inclusive bounds, uses median P50 and nearest-rank P90 correction after enough inliers, and otherwise exposes an explicit partial-quality cold start. Unavailable plans retain absent percentiles rather than zero distance.
- C8a added a frozen typed diagnostics snapshot and a versioned JSON-safe allowlist containing only aggregate counts, stable filter/route-failure categories, quality and generation time.
- C8a prevents profile names, entity/event identifiers, event text, addresses, coordinates, provider details and credentials from entering diagnostics by construction; count consistency, immutability and timezone requirements are validated.
- C8b added minimal Home Assistant custom-integration and HACS metadata, enabled a schema-version-1 config flow, and added matching source/English strings for its single required profile-name input.
- C8b creates each profile as a separate entry with its name used only as the title and a fresh empty data mapping. It assigns no unique ID, so multiple profiles remain supported, and introduces no calendar, location, vehicle, route, credential or threshold default.
- C8c added frozen profile state and config-entry-scoped storage keys plus schema-version-1 JSON-safe serialization for complete immutable plan revisions, pending days and closed actuals.
- C8c decoding rebuilds validated domain values, rejects unknown schema versions and malformed or duplicate records, and preserves unavailable plans without fabricating route or distance values.
- C8d added a dependency-free profile coordinator over typed read-only source and config-entry-scoped storage protocols. Every load/save is explicitly addressed by config-entry identifier, while source reads receive only immutable prior state.
- C8d validates unique chronologically ordered forecast dates, persists the next state before publishing an immutable snapshot, and preserves the last published data when a source read or storage save fails.
- C8e added one passive, entry-scoped forecast-distance sensor over the coordinator's immutable snapshot. It exposes the earliest forecast's conservative P90 distance in kilometres without implementing polling, update or action methods.
- C8e keeps missing distance as an unknown value rather than zero and limits attributes to service date, P50 distance, quality and generation time. Arbitrary reason text and source identifiers are not projected.
- C8f added the Home Assistant config-entry diagnostics adapter over the existing typed aggregate projection. It reads only an entry-scoped diagnostics source and never traverses config-entry metadata, data, options, coordinator state or raw storage.
- C8f added one immutable runtime composition root so the sensor and diagnostics adapters consume separate typed read-only boundaries from the same config entry. Diagnostics source failures propagate without a fallback object dump.
- C9a added one least-privilege GitHub Actions quality job for pushes and pull requests, with read-only repository permission, concurrency cancellation, a ten-minute timeout and immutable action commit pins.
- C9a pins Ruff 0.16.4, Pyright 1.1.411 and pytest 9.1.1, runs the standard-library checkpoint/config validator and all 77 tests, lints the complete integration package, and strictly type-checks the dependency-free domain/coordinator/storage core.
- C9b expanded Ruff lint and format enforcement to every tracked Python file, resolved all 33 previously reported repository findings, and added a contract test that makes the strict Pyright boundary explicit rather than implying repository-wide type coverage.
- C9b completed the phase-1 configuration/documentation audit without changing runtime metadata, schemas, defaults or dependencies. Existing isolated contracts continue to validate manifest/HACS metadata and exact source/English translation parity.
- P1 added real `async_setup_entry` and `async_unload_entry` hooks that create one isolated fail-closed runtime per config entry and forward only the sensor platform.
- P1 clears runtime data only after successful platform unload and preserves it after failed unload so still-loaded entities retain their boundary. Pending source, storage and diagnostics adapters perform no I/O and fail explicitly rather than fabricating forecasts or diagnostics.
- P1 expanded strict Pyright coverage to the lifecycle module using minimal isolated Home Assistant contract stubs; no Home Assistant package or production instance was installed or accessed.
- P2 added a config-entry-scoped Home Assistant Store adapter that wraps the existing schema-version-1 codec in a private, atomic store and rejects every mismatched entry identifier.
- P2 treats only an absent store as explicit empty profile state; malformed and unsupported payloads fail closed without deletion or overwrite. Synthetic tests prove entry isolation, restoration through a fresh runtime/store instance after restart, and retention across lifecycle unload.
- P3 added an explicit schema-1.2 calendar-selection contract: each new profile
  stores a non-empty ordered list of unique `calendar` entity identifiers, while
  schema-1.1 entries migrate to an empty legacy-unconfigured marker rather than a
  guessed behavioral default.
- P3 added a typed read-only Home Assistant calendar source that queries one
  explicit aware window, normalizes timed and all-day `CalendarEvent` values into
  frozen domain events, keeps provider-specific online classification injected,
  and converts missing entities, identifiers, malformed events and read failures
  to stable private-data-free failures.
- P4 added a reusable test-only deterministic composition harness that connects
  the P3 calendar adapter to existing explicit filter, planning, fake-routing,
  forecast, coordinator, storage-fake and passive-sensor contracts without adding
  a production runtime source or choosing hidden policy defaults.
- P4 proves a complete 10 km synthetic route produces the explicit cold-start
  12.5 km P90 sensor value, while a typed transient route failure is persisted as
  a partial immutable revision and projects unavailable/unknown distance rather
  than zero. Sensor attributes exclude synthetic event text, location text and the
  config-entry identifier.
- P5 adds an isolated real Home Assistant compatibility suite separate from the
  dependency-free tests. Its exactly pinned harness installs Home Assistant
  2026.8.1 on Python 3.14 and drives the user config flow through the real flow
  manager and entity-selector schema before asserting schema-1.2 entry creation.
- P5 adds a least-privilege CI compatibility job without credentials, network
  providers, production mounts or runtime service calls; its sole profile,
  calendar identifier and input text are synthetic.

## Active checkpoint

P5 — Real Home Assistant config-flow compatibility testing is complete.

Next bounded checkpoint: exercise config-entry setup/unload and passive sensor
registration/state through Home Assistant 2026.8.1's real lifecycle and state
machine. Use only synthetic fixtures in the isolated compatibility environment;
do not install into or inspect production Home Assistant. Hassfest/HACS
validation and the reproducible install ZIP plus `TESTING.md` remain later
checkpoints.

## Verification evidence

C0 verification on 2026-08-25:

```text
python3 -m compileall -q scripts                  PASS
python3 scripts/check_checkpoint.py               PASS
scripts/codex_usage.py via Hermes Python           PASS
Apache-2.0 system license copy                     present
```

C1 verification on 2026-08-25:

```text
python3 scripts/check_checkpoint.py               PASS
python3 -m compileall -q scripts                   PASS
git diff --check                                  PASS
local Markdown link validation                    PASS
full diff privacy/secret/scope review              PASS
```

C2 TDD and verification on 2026-08-25:

```text
python3 -m unittest discover -s tests -v           RED: missing domain package
python3 -m unittest discover -s tests -v           PASS (9 tests)
python3 scripts/check_checkpoint.py                PASS (includes compileall + 9 tests)
git diff --check                                  PASS
```

The C2 test suite uses only synthetic identifiers and coordinates and makes no network, Home Assistant, route-provider or vehicle-service calls. Ruff, Pyright and pytest executables are not installed in the local environment; C2 uses the standard library test runner, while tool policy is recorded in `pyproject.toml` for later CI/bootstrap work.

Configuration review for C2: `pyproject.toml` now explicitly sets pre-alpha project metadata, Apache-2.0, Python 3.13 compatibility and Ruff/Pyright policy. The pure package lives under `custom_components/mobility_forecast`, includes `py.typed`, and has no runtime dependencies or build backend. `.gitignore`, package inclusion and test discovery were reviewed; no additional ignore or test configuration was needed. Home Assistant `manifest.json`, `hacs.json`, strings/translations, workflows, config-flow schemas and storage schemas remain intentionally absent until their planned checkpoints. No Home Assistant option, schema version, threshold or behavioral default was introduced.

C3 TDD and verification on 2026-08-25–26:

```text
python3 -m unittest tests.test_calendar_filters -v  RED: filter module absent
python3 -m unittest tests.test_calendar_filters -v  PASS (7 tests)
python3 -m unittest discover -s tests -v             PASS (16 tests)
python3 scripts/check_checkpoint.py                  PASS
git diff --check                                     PASS
```

All C3 fixtures use synthetic text, identifiers and locations. Tests and implementation are pure and make no network, Home Assistant, route-provider, vehicle-service or notification calls. Ruff, Pyright and pytest remain unavailable locally; the configured standard-library suite is the executable verification path.

Configuration review for C3: `pyproject.toml`, `.gitignore`, package layout and checkpoint test discovery remain applicable and required no changes. `manifest.json`, `hacs.json`, strings/translations, workflows, config-flow schemas and storage schemas remain intentionally absent until their planned checkpoints. C3 introduces no Home Assistant setting, schema version or silent default: all five filter-policy fields are required domain inputs, and normalized `all_day` and `is_online` flags are now required on `SourceEvent`.

C4 TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_location_resolution -v  RED: location contract absent
python3 -m unittest tests.test_location_resolution -v  PASS (9 tests)
python3 -m unittest discover -s tests -v                PASS (25 tests)
python3 scripts/check_checkpoint.py                     PASS
git diff --check                                        PASS
```

All C4 fixtures use synthetic identifiers and coordinates. The resolver is pure and makes no network, Home Assistant, route-provider, vehicle-service or notification calls. Ruff, Pyright and pytest executables remain unavailable locally; the standard-library suite is the executable verification path. Independent diff review found no secrets, personal data, external calls or scope outside C4.

Configuration review for C4: `pyproject.toml`, `.gitignore`, package layout and checkpoint test discovery were reviewed and require no changes. `manifest.json`, `hacs.json`, strings/translations, workflows, config-flow schemas and storage schemas remain intentionally absent until their planned checkpoints. C4 changes no persisted or Home Assistant schema and establishes no silent numeric default: all three start thresholds and the end-fallback choice are required constructor inputs. `docs/ARCHITECTURE.md` now documents the exact domain behavior and preserves C8 ownership of user-facing defaults.

C5 TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_routing -v            RED: routing exports absent
python3 -m unittest tests.test_routing -v            PASS (8 tests)
python3 -m unittest tests.test_routing.CachedRoutingTests.test_cache_rejects_future_evaluation_and_provider_mismatch -v
                                                       RED: cache direction unchecked
python3 -m unittest tests.test_routing -v            PASS (8 tests)
python3 -m unittest tests.test_routing.RouteContractTests.test_cache_key_is_directional_private_and_option_sensitive -v
                                                       RED: provider namespace absent
python3 -m unittest tests.test_routing -v            PASS (8 tests)
python3 -m unittest discover -s tests -v             PASS (33 tests)
python3 scripts/check_checkpoint.py                  PASS
git diff --check                                     PASS
ruff / pyright / pytest executable discovery         unavailable
```

All C5 endpoints, provider names and key material are synthetic. The provider and cache fakes are in-memory only; tests and implementation make no network, Home Assistant, vehicle-service or notification calls. Independent diff review found no credentials, personal data, raw endpoint data in cache keys, external calls or scope outside C5.

Configuration review for C5: `pyproject.toml`, `.gitignore`, package layout and standard-library test discovery were reviewed and require no changes. `manifest.json`, `hacs.json`, strings/translations, workflows, config-flow schemas and storage schemas remain intentionally absent until their planned checkpoints. C5 changes no persisted or Home Assistant schema and establishes no silent cache or routing default: both route option flags, both cache age limits, a stable provider/config namespace and profile-local privacy key material are required inputs. Cache persistence/key rotation and user-facing defaults remain C8 responsibilities.

C6 TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_planning -v       RED: planning exports absent
python3 -m unittest tests.test_planning -v       PASS (7 tests)
python3 -m unittest discover -s tests -v         PASS (40 tests)
python3 scripts/check_checkpoint.py              PASS (40 tests)
git diff --check                                PASS
ruff / pyright / pytest executable discovery    unavailable
```

All C6 calendars, identifiers, locations, provider responses and revision data are synthetic. The planner is pure apart from its typed route-provider boundary, which is exercised only through the exact in-memory deterministic fake. Tests make no network, Home Assistant, vehicle-service or notification calls. Independent diff review found no credentials, personal data, production calls, copied upstream implementation or scope outside C6.

Configuration review for C6: `pyproject.toml`, `.gitignore`, package layout and standard-library test discovery were reviewed and require no changes. `manifest.json`, `hacs.json`, strings/translations, GitHub workflows, config-flow schemas and storage schemas remain intentionally absent until C8/C9. C6 changes no persisted or Home Assistant schema and introduces no silent policy/default: the normalized deduplication key, destination reason, initial origin, route options, provider and revision/source timestamps are explicit inputs. Persistent plan repository schema and migrations remain C8 responsibilities.

C7 TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_actuals_forecasting -v
                                                     RED: actuals exports absent
python3 -m unittest tests.test_actuals_forecasting.RobustForecastTests.test_rejects_duplicate_or_nonhistorical_training_actuals -v
                                                     RED: invalid history accepted
python3 -m unittest tests.test_actuals_forecasting -v
                                                     PASS (10 tests)
python3 -m unittest discover -s tests -v             PASS (50 tests)
python3 scripts/check_checkpoint.py                  PASS (50 tests)
python3 -m compileall -q custom_components tests    PASS
git diff --check                                     PASS
ruff / pyright / basedpyright / pytest discovery    unavailable
```

All C7 revision identifiers, times, routes and odometer values are synthetic. The implementation is frozen, typed, dependency-free domain logic and exposes no Home Assistant, storage, network, route-provider, vehicle-refresh, service or notification path. Independent diff review found no credentials, addresses, coordinates from a real location, calendar contents, personal data or scope outside C7.

Configuration review for C7: `pyproject.toml`, `.gitignore`, package layout and standard-library test discovery were reviewed and require no changes. `manifest.json`, `hacs.json`, strings/translations, GitHub workflows, config-flow schemas and storage schemas remain intentionally absent until C8/C9. C7 changes no persisted or Home Assistant schema and introduces no silent behavioral default: maximum sample age, maximum daily distance, minimum history count, lower/upper correction bounds and cold-start P90 multiplier are all required inputs. Profile-scoped serialization, schema versioning and migration remain C8 responsibilities.

C8a TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_diagnostics -v       RED: diagnostics module absent
python3 -m unittest tests.test_diagnostics -v       PASS (3 tests)
python3 -m unittest discover -s tests -v            PASS (53 tests)
python3 scripts/check_checkpoint.py                 PASS (53 tests)
python3 -m compileall -q custom_components tests   PASS
git diff --check                                    PASS
ruff / pyright / basedpyright / pytest discovery   unavailable
```

All C8a inputs are synthetic aggregate values. The diagnostics projection is dependency-free and has no Home Assistant, storage, network, route-provider, vehicle-refresh, service or notification path. Independent diff review found no credentials, personal data, raw private fields, external calls or scope beyond the C8 diagnostics sub-slice.

Configuration review for C8a: `pyproject.toml`, `.gitignore`, package layout and standard-library test discovery were reviewed and require no changes. `manifest.json`, `hacs.json`, strings/translations, GitHub workflows, config-flow schemas and storage schemas remain absent because this bounded slice adds no loadable Home Assistant adapter, configuration or persistence. Adding metadata now would either claim a config flow that does not exist or invent unavailable repository URLs. No default or persisted schema changed. Diagnostics payload schema version 1 is an explicit output contract, not a Home Assistant config/storage schema.

C8b TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_config_flow -v     RED: flow/metadata absent (4 errors)
python3 -m unittest tests.test_config_flow -v     PASS (4 tests)
python3 -m unittest discover -s tests -v          PASS (57 tests)
python3 scripts/check_checkpoint.py               PASS (57 tests)
python3 -m compileall -q custom_components tests PASS
git diff --check                                  PASS
ruff / pyright / basedpyright / pytest / hassfest discovery
                                                    unavailable
```

The C8b flow was executed only against in-process synthetic Home Assistant and Voluptuous stand-ins; no Home Assistant installation, entity, route provider, vehicle service, notification path, credential or personal data was accessed. The two synthetic profile names are non-personal placeholders. Independent diff review found no secrets, addresses, coordinates, identifiers, external calls or scope beyond metadata, config-flow schema, strings, tests and checkpoint documentation.

Configuration review for C8b: `pyproject.toml`, `.gitignore`, package inclusion and standard-library test discovery were reviewed and require no changes. `manifest.json` now declares domain/name/version `0.0.0`, config-flow support and service integration type; `hacs.json` contains only the required display name. Repository documentation and issue URLs and code-owner handles remain intentionally absent rather than invented. `strings.json` and `translations/en.json` exactly cover the one required name field. Config entries declare schema version 1/minor version 1 and persist no data yet, so no migration or behavioral default is introduced. Storage schemas and workflows remain deferred to later C8/C9 checkpoints.

C8c TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_storage -v       RED: storage module absent
python3 -m unittest tests.test_storage -v       PASS (5 tests)
python3 -m unittest discover -s tests -v        PASS (62 tests)
python3 scripts/check_checkpoint.py             PASS (62 tests)
python3 -m compileall -q custom_components tests PASS
git diff --check                                PASS
ruff / pyright / basedpyright / pytest / hassfest discovery
                                                 unavailable
```

All C8c identifiers, coordinates, provider labels, timestamps and measurements are synthetic. The codec is dependency-free and performs no Home Assistant, filesystem, network, route-provider, vehicle-refresh, service or notification call. Independent diff review found no credentials, real personal data, external calls or scope beyond profile state serialization, tests and checkpoint documentation. Raw encoded state intentionally contains operational endpoint/event identifiers and coordinates required for exact plan reconstruction; the contract documents that these private profile-local payloads must never enter diagnostics or logs.

Configuration review for C8c: `pyproject.toml`, `.gitignore`, package inclusion, test discovery, `manifest.json`, `hacs.json`, config-flow schema version 1/minor version 1, and source/English strings were reviewed and require no change. GitHub workflows remain deferred to C9. Storage schema version 1 is the first persisted-state contract and changes no existing default or config-entry data. There is therefore no legacy payload to migrate; unknown versions fail closed, and any future version must add an explicit migration and tests before acceptance.

C8d TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_coordinator -v   RED: coordinator module absent
python3 -m unittest tests.test_coordinator -v   PASS (6 tests)
python3 -m unittest discover -s tests -v        PASS (68 tests)
python3 scripts/check_checkpoint.py             PASS (68 tests)
python3 -m compileall -q custom_components tests PASS
git diff --check                                PASS
ruff / pyright / basedpyright / pytest / hassfest discovery
                                                 unavailable
```

All C8d entry identifiers, forecast dates, measurements and failures are synthetic. The coordinator and its deterministic fakes make no Home Assistant, filesystem, network, route-provider, vehicle-refresh, service or notification call. Independent diff review found no credentials, personal data, external calls or scope beyond the coordinator contract, tests, architecture and checkpoint documentation.

Configuration review for C8d: `pyproject.toml`, `.gitignore`, package inclusion, test discovery, `manifest.json`, `hacs.json`, config-entry schema version 1/minor version 1, storage schema version 1, and source/English strings were reviewed and require no change. GitHub workflows remain deferred to C9. The coordinator introduces no Home Assistant setting, persisted field, schema migration, translation or behavioral threshold/default; it consumes the existing typed `ProfileState` and publishes only immutable forecasts and generation time.

C8e TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_sensor -v        RED: sensor module absent (4 errors)
python3 -m unittest tests.test_sensor -v        RED: translation/attribute allowlist absent (1 error, 1 failure)
python3 -m unittest tests.test_sensor -v        PASS (5 tests)
python3 -m unittest discover -s tests -v        PASS (73 tests)
python3 scripts/check_checkpoint.py             PASS (73 tests)
python3 -m compileall -q custom_components tests PASS
git diff --check                                PASS
ruff / pyright / basedpyright / pytest / hassfest discovery
                                                 unavailable
```

All C8e entry identifiers, dates, measurements and quality values are synthetic. Tests load the adapter only against in-process Home Assistant stand-ins and make no production Home Assistant, filesystem, network, route-provider, vehicle-refresh, service or notification call. The sensor implements no polling, update or action method. Its fixed attributes exclude config-entry, source, entity, event, location and provider identifiers plus arbitrary reason text; unavailable distance remains `None`, not zero.

Configuration review for C8e: `pyproject.toml`, `.gitignore`, package inclusion/test discovery, `manifest.json`, `hacs.json`, config-entry schema version 1/minor version 1 and storage schema version 1 were reviewed and require no change. Source strings and `translations/en.json` now add only the reviewed `forecast_distance` entity name and remain exactly equal. GitHub workflows remain deferred to C9. The sensor introduces no config option, persisted field, migration, polling interval, threshold or behavioral default; P90 is explicitly the conservative primary presentation already carried by the domain forecast.

C8f TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_ha_diagnostics -v
                                                   RED: adapter/runtime exports absent
python3 -m unittest tests.test_ha_diagnostics -v   PASS (2 tests)
python3 -m unittest tests.test_sensor -v           PASS (5 tests)
python3 -m unittest discover -s tests -v           PASS (75 tests)
python3 scripts/check_checkpoint.py                PASS (75 tests)
python3 -m compileall -q custom_components tests  PASS
git diff --check                                   PASS
ruff / pyright / basedpyright / pytest / hassfest discovery
                                                   unavailable
```

All C8f entry metadata, configuration values, timestamps and aggregate counts are synthetic. The adapter and its deterministic source fake make no production Home Assistant, filesystem, network, route-provider, vehicle-refresh, service or notification call. The privacy test places synthetic private values in config-entry metadata, data and options and proves none enter the JSON payload; source failure is tested to propagate rather than trigger an object dump. Independent diff review found no credentials, personal data, external calls or scope beyond the runtime/diagnostics adapter, the required sensor runtime-data compatibility update, tests and checkpoint documentation.

Configuration review for C8f: `pyproject.toml`, `.gitignore`, package inclusion/test discovery, `manifest.json`, `hacs.json`, config-entry schema version 1/minor version 1, storage schema version 1, and source/English strings were reviewed and require no change. GitHub workflows remain deferred to C9. The diagnostics payload remains schema version 1; the runtime composition root is in-memory only. No default, config option, persisted field, migration, translation or integration metadata changed.

C9a TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_ci_configuration -v
                                                    RED: workflow/lock absent (2 errors)
python3 -m unittest tests.test_ci_configuration -v PASS (2 tests)
python3 scripts/check_checkpoint.py                PASS (77 tests included)
ruff check custom_components/mobility_forecast    PASS
pyright                                            PASS (0 errors, 0 warnings)
pytest                                             PASS (77 tests)
git diff --check                                  PASS (via checkpoint validator)
```

The C9a workflow has no manual or privileged trigger, write permission, secret reference, publication step or untrusted event-data interpolation. It uses only repository checkout, Python setup and local checks; tests remain synthetic and no production Home Assistant, route provider, vehicle service, notification, credential or personal data was accessed. Local validation used an ignored in-repository tool directory because the host lacks `ensurepip`; CI uses Python's normal pip in the isolated GitHub runner.

Configuration review for C9a: `pyproject.toml` now gives pytest an explicit `tests` discovery root and limits strict Pyright enforcement to the dependency-free domain, coordinator and storage modules that can be validated without installing Home Assistant. Ruff policy and Python 3.13 remain unchanged; the workflow lints the entire integration package. `requirements-dev.txt` pins the three direct quality tools, while both GitHub actions are pinned to immutable commits. `.gitignore`, package inclusion, `manifest.json`, `hacs.json`, config-entry schema version 1/minor version 1, storage schema version 1 and source/English strings were reviewed and require no change. No runtime dependency, behavioral default, persisted field, schema version, translation or integration metadata changed.

C9b TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_ci_configuration -v
                                                    RED: repository format check absent
ruff check .                                       RED: 33 repository findings
ruff check .                                       PASS
ruff format --check .                              PASS (43 files)
python3 -m unittest tests.test_ci_configuration -v PASS (3 tests)
python3 -m unittest discover -s tests -v            PASS (78 tests)
python3 scripts/check_checkpoint.py                 PASS (78 tests included)
PYTHONPATH=.venv/site python3 -m pytest             PASS (78 tests)
PYTHONPATH=.venv/site python3 -m pyright            PASS (0 errors, 0 warnings)
PYTHONPATH=.venv/site python3 -m pyright custom_components/mobility_forecast tests scripts
                                                    AUDIT: 104 strict findings
controller prompt semantic comparison              PASS (exact value preserved)
```

The broad Pyright audit is deliberately non-gating: the configured strict boundary remains the dependency-free domain/coordinator/storage core. The 104 broader findings are concentrated in Home Assistant adapters loaded without Home Assistant type information and dynamic synthetic module/config fixtures; silently weakening strict mode or installing production Home Assistant was rejected. The next lifecycle checkpoint must establish isolated typed Home Assistant contract fixtures before expanding adapter type coverage.

All formatting and lint changes are behavior-neutral; the controller prompt was compared to its committed predecessor as an evaluated Python value and is identical. Tests remain synthetic and no production Home Assistant, route provider, vehicle service, notification, credential or personal data was accessed. The complete diff was reviewed for workflow injection, secrets, private data, external calls and scope creep.

Configuration review for C9b: `pyproject.toml`, Python/tool versions, `requirements-dev.txt`, `.gitignore`, package/test discovery, `manifest.json`, `hacs.json`, source/English strings, config-entry schema version 1/minor version 1 and storage schema version 1 were reviewed. Only the existing quality workflow changed: Ruff now covers the repository and enforces formatting. Action pins, permissions and triggers are unchanged. No dependency, runtime metadata, translation, behavioral default, persisted field or schema version changed. Hassfest/Home Assistant validation remains unavailable without adding the intentionally absent Home Assistant development dependency; existing isolated metadata/config-flow/translation tests pass instead.

P1 TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_lifecycle -v          RED: lifecycle hooks absent
python3 -m unittest tests.test_lifecycle -v          PASS (4 tests)
python3 scripts/check_checkpoint.py                  PASS (82 tests included)
PYTHONPATH=.venv/site python3 -m pytest              PASS (82 tests)
PYTHONPATH=.venv/site python3 -m pyright             PASS (0 errors; 2 expected missing-source warnings for isolated stubs)
PYTHONPATH=.venv/site python3 -m ruff check .        PASS
PYTHONPATH=.venv/site python3 -m ruff format --check .
                                                     PASS (48 files)
git diff --check                                    PASS
```

All P1 entry identifiers and fixtures are synthetic. Lifecycle setup constructs only entry-scoped in-memory boundaries and forwards the passive sensor; it creates no refresh task, timer, update interval, filesystem access, network call, route-provider request, vehicle action, notification or credential path. Pending source, storage and diagnostics calls fail with fixed non-private errors. Independent diff review found no secret, credential, personal data, production call or scope beyond lifecycle, isolated typing fixtures, quality configuration and checkpoint documentation.

Configuration review for P1: `pyproject.toml`, tool versions, `requirements-dev.txt`, `.gitignore`, package/test discovery, quality workflow, `manifest.json`, `hacs.json`, source/English strings, config-entry schema version 1/minor version 1 and storage schema version 1 were reviewed. Strict Pyright now includes the lifecycle module and resolves its Home Assistant surface through repository-local `.pyi` contracts under `typings/`; no runtime or development dependency was added. Runtime metadata, translations, config flow, defaults, persisted fields and schema versions are unchanged. The only platform list is the existing read-only sensor.

P2 TDD and verification on 2026-08-26:

```text
python3 -m unittest tests.test_ha_storage -v
                                                     RED: adapter module absent (4 errors)
python3 -m unittest tests.test_ha_storage -v          PASS (4 tests)
python3 -m unittest tests.test_lifecycle.ConfigEntryLifecycleTests.test_successful_unload_clears_runtime_after_platform_unload -v
                                                     RED: pending storage failed before source
python3 -m unittest tests.test_lifecycle -v           PASS (4 tests)
python3 scripts/check_checkpoint.py                  PASS (86 tests included)
PYTHONPATH=.venv/site python3 -m pytest              PASS (86 tests)
PYTHONPATH=.venv/site python3 -m pyright             PASS (0 errors; 5 expected missing-source warnings for isolated stubs)
PYTHONPATH=.venv/site python3 -m ruff check .        PASS
PYTHONPATH=.venv/site python3 -m ruff format --check .
                                                     PASS (52 files)
git diff --check                                    PASS
```

All P2 entry identifiers, state, coordinates, timestamps and backing stores are synthetic in-process fixtures. The adapter uses only Home Assistant's typed Store contract fixture; no production Home Assistant, filesystem, network, route provider, vehicle service, notification, credential or personal data was accessed. Setup constructs the Store without I/O, no refresh schedule was added, and unload never invokes Store removal. Independent diff review found no secrets, private real-world data, production calls or scope beyond the Store adapter, lifecycle composition, typing fixtures, tests and checkpoint documentation.

Configuration review for P2: `pyproject.toml`, Python/tool versions, `requirements-dev.txt`, `.gitignore`, package/test discovery, quality workflow, `manifest.json`, `hacs.json`, config-entry schema version 1/minor version 1, storage schema version 1, config flow and source/English strings were reviewed. Strict Pyright now includes the runtime and Store adapter through a minimal repository-local Store contract. No dependency, runtime metadata, translation, config option, behavioral threshold, persisted field or schema version changed. The adapter deliberately selects Home Assistant Store privacy and atomic-write flags; the only new initialization rule is empty immutable state when no store exists, while any present invalid payload still fails closed.

P3 TDD and verification on 2026-09-01:

```text
/usr/bin/python3 -m unittest tests.test_ha_calendar_source tests.test_config_flow -v
                                                     RED: 2 failures, 2 errors
/usr/bin/python3 -m unittest tests.test_ha_calendar_source tests.test_config_flow tests.test_lifecycle -v
                                                     PASS (16 focused tests)
/usr/bin/python3 scripts/check_checkpoint.py          PASS (94 tests included)
PYTHONPATH=.venv/site python3 -m pytest                PASS (94 tests)
PYTHONPATH=.venv/site python3 -m ruff check .          PASS
PYTHONPATH=.venv/site python3 -m ruff format --check . PASS (54 files)
PYTHONPATH=.venv/site python3 -m pyright               PASS (0 errors; 6 expected missing-source warnings for isolated stubs)
git diff --check                                      PASS
```

All P3 profile names, entity identifiers, event identifiers, text, locations and
timestamps are synthetic. Tests use in-process calendar/entity contracts and do
not import or access a production Home Assistant instance, filesystem state,
calendar content, credentials, network, route provider, vehicle, physical service
or notification path. The adapter exposes only calendar reads; it has no write or
service method and adds no task, polling interval or runtime refresh. Home
Assistant compatibility was checked against the official developer documentation
and the `CalendarEvent`, `CalendarEntity`, `ConfigEntry` and selector source at the
Home Assistant 2026.8.1 tag.

Configuration review for P3: config-entry schema version 1 advances from minor
version 1 to 2 because a required persisted `calendar_entity_ids` list is added.
The field is required because each profile owns its sources; requiring explicit
selection avoids a hidden calendar default. New entries validate a non-empty,
ordered, duplicate-free list in the `calendar` domain. Existing 1.1 entries had
empty data and migrate only to an explicit empty legacy-unconfigured marker; no
calendar can be inferred safely, and strict source decoding rejects that marker.
A reconfiguration/repair flow for legacy entries remains required before runtime
source composition. Source and English translations add labels and descriptions
for the new field and remain identical. `pyproject.toml` extends strict Pyright to
the new typed adapter. Tool pins, dependencies, storage schema 1, manifest,
`hacs.json`, workflow, sensor platform and package metadata are unchanged.

P4 TDD and verification on 2026-09-01:

```text
/usr/bin/python3 -m unittest tests.test_synthetic_smoke_pipeline -v
                                                     RED: missing synthetic harness
/usr/bin/python3 -m unittest tests.test_synthetic_smoke_pipeline -v
                                                     PASS (2 smoke tests)
/usr/bin/python3 -m unittest discover -s tests -v     PASS (96 tests)
/usr/bin/python3 scripts/check_checkpoint.py          PASS (96 tests included)
PYTHONPATH=.venv/site python3 -m pytest                PASS (96 tests)
PYTHONPATH=.venv/site python3 -m ruff check .          PASS
PYTHONPATH=.venv/site python3 -m ruff format --check . PASS
PYTHONPATH=.venv/site python3 -m pyright               PASS (0 errors; 6 expected missing-source warnings)
git diff --check                                      PASS
```

Every P4 calendar entity, event, identifier, text value, location, coordinate,
route, timestamp, config-entry identifier and storage value is synthetic. The
calendar entity, route provider, storage and Home Assistant sensor contracts are
in-process fakes with no filesystem, network, credential, production Home
Assistant, geocoder, vehicle, physical service or notification path. The harness
is under `tests/` and cannot be selected by runtime composition. Independent diff
review found no secret, personal data, production call or scope beyond the smoke
harness, its two end-to-end contract tests and checkpoint documentation.

Configuration review for P4: `pyproject.toml`, Python/tool pins,
`requirements-dev.txt`, `.gitignore`, package/test discovery, quality workflow,
manifest, `hacs.json`, config-entry schema 1.2, storage schema 1, config flow,
source/English translations and sensor metadata were reviewed and require no
change. No runtime module, dependency, metadata, translation, config field,
default, migration, persisted schema, polling behavior or physical capability was
added. The explicit synthetic policy numbers and endpoint mappings exist only in
test fixtures and do not establish product defaults.

P5 TDD and verification on 2026-09-01:

```text
/usr/bin/python3 -m unittest tests.test_ci_configuration.QualityWorkflowTests.test_quality_workflow_runs_every_configured_check -v
                                                     RED: real-HA CI job absent
/usr/bin/python3 -m unittest tests.test_ci_configuration -v
                                                     PASS (3 contract tests)
docker run ... python:3.14-slim ... pytest ... tests_real_ha
                                                     PASS (1 test; HA 2026.8.1)
/usr/bin/python3 scripts/check_checkpoint.py          PASS (96 tests included)
PYTHONPATH=.venv/site python3 -m pytest                PASS (96 tests)
PYTHONPATH=.venv/site python3 -m ruff check .          PASS
PYTHONPATH=.venv/site python3 -m ruff format --check . PASS (59 files)
PYTHONPATH=.venv/site python3 -m pyright               PASS (0 errors; 6 expected missing-source warnings)
git diff --check                                      PASS
```

The compatibility test runs in a disposable Python 3.14 container with the
repository mounted read-only and `PYTHONDONTWRITEBYTECODE=1`. Release 0.13.355 of
`pytest-homeassistant-custom-component` requires Home Assistant 2026.8.1 exactly;
the test independently asserts the installed distribution version before using
Home Assistant's real config-flow manager, `EntitySelector` validation and config
entry result. The input contains only a synthetic profile name and synthetic
calendar entity identifier. No production Home Assistant path, credential,
calendar state, address, coordinate, route/geocoder, vehicle, physical service,
notification or external runtime provider was accessed.

Configuration review for P5: `requirements-ha-test.txt` adds one exact direct test
harness pin in a dependency-isolated CI job on Python 3.14, because Home Assistant
2026.8.1 and its matching harness require Python 3.14 while the dependency-free
quality job remains on Python 3.13. The compatibility suite is outside default
pytest discovery, so `/usr/bin/python3 scripts/check_checkpoint.py` and the pinned
local quality equivalents remain independent of Home Assistant. A namespace
`custom_components/__init__.py` is test-import scaffolding and is outside the
future integration-only ZIP. Manifest, HACS metadata, config schema 1.2, storage
schema 1, translations, runtime behavior, defaults and production dependencies
are unchanged. The CI workflow retains read-only permissions, immutable action
pins and no secret or publication path.

## Current decisions

- Name/domain: Mobility Forecast / `mobility_forecast`.
- License/delivery: Apache-2.0 clean-room implementation, HACS-first.
- Config model: one isolated config entry per forecast profile; multiple entries supported.
- V1 is read-only/advisory and excludes notifications, price/solar optimization and every physical action.
- Start and end locations use independent policies. Dynamic vehicle location is passive, freshness/quality gated and fallback based; no wake or refresh request is allowed.
- The domain uses provider-neutral typed boundaries. Google Routes is the intended first production route adapter; unattended tests use deterministic fakes only.
- Route and input failures remain partial, stale or unavailable and never become zero distance or false readiness.
- Historical plan revisions are immutable so later calendar edits do not rewrite training truth.
- Domain value objects are frozen and dependency-free. Operational private fields remain available to pure logic but are omitted from representations to reduce accidental disclosure.
- Calendar filtering is deterministic and profile-policy driven. Include/exclude terms use case-insensitive substring matching over summary and description only; previews expose aggregate counts and stable reason codes only.
- Passive start GPS is accepted only within explicit inclusive age, accuracy and trip-horizon gates. Start and end fallback decisions are independent; fallbacks are partial rather than silently complete.
- Routing is directional and asynchronous behind typed provider/cache protocols. Cache keys are profile-keyed HMAC digests of all route-affecting inputs; fresh/stale limits are explicit, and stale fallback retains both stale quality and the refresh-failure category.
- Itinerary assembly uses explicit normalized deduplication keys, deterministic stop ordering and known-destination chaining. Conflicting duplicates fail closed, degraded legs remain explicit, and revision history is append-only and immutable.
- Passive actuals capture the latest complete revision that existed when a day opened and never rematch later edits. Only fresh, monotonic and explicitly distance-bounded odometer closures become complete training actuals.
- Forecast correction uses only unique earlier-day actuals. Explicit ratio bounds reject outliers; sufficient inliers use median P50 and nearest-rank P90, while cold start is partial and uses an explicit conservative multiplier.
- Diagnostics use a versioned aggregate allowlist rather than recursively dumping and redacting private runtime/configuration objects.
- Config flow creates one entry per profile from a required display name and an
  explicit non-empty ordered calendar selection, deliberately permits multiple
  entries and introduces no source or threshold default.
- Durable state uses config-entry identifiers rather than profile titles for isolation. Storage schema version 1 round-trips validated immutable revisions, pending days and actuals; unsupported versions are rejected until explicitly migrated.
- Coordinator refreshes are profile-scoped transactions: load prior state, read one typed source update, persist next state, then publish an immutable ordered forecast snapshot. Failed reads or saves do not replace published data.
- The first entity is one entry-scoped passive distance sensor. It presents the earliest forecast's P90 distance, keeps unavailable distance unknown, and exposes only a fixed non-identifying attribute allowlist.
- Home Assistant diagnostics consume only a typed entry-scoped aggregate source. Config-entry fields and runtime objects are not recursively dumped, and source failures remain explicit.
- Config-entry setup owns one isolated runtime and forwards only the sensor platform. Unload releases that runtime only when platform unload succeeds; pending adapter boundaries fail closed and schedule no work.
- Durable runtime state uses one private, atomic Home Assistant Store keyed only by config-entry identifier. Missing storage starts from explicit empty state; restart restores decoded immutable state, cross-entry calls fail, and unload retains persisted data.
- Config-entry schema 1.2 requires every new profile to explicitly select one or
  more ordered unique calendar entities. Schema-1.1 entries migrate to a
  deliberately invalid empty marker rather than guessing a source.
- Calendar normalization reads only configured `CalendarEntity` objects for an
  explicit aware window. It maps Home Assistant 2026.8.1 timed/all-day events to
  frozen source events, requires provider identity, injects online classification
  policy and emits stable private-data-free failures.
- The synthetic smoke harness proves the existing calendar, filtering, planning,
  fake-routing, forecast, coordinator, persistence and sensor contracts compose
  across one complete path and one route-failure path. It is test-only evidence,
  not the production runtime composition and not proof of real forecasting.
- Real Home Assistant compatibility tests are isolated from the dependency-free
  suite and pin the matching test harness for Home Assistant 2026.8.1. The first
  slice proves only config-flow form validation and entry creation through Home
  Assistant's real flow manager; it does not yet prove lifecycle or entity state.

## Remaining risks and deferred details

- C2–C7 define the pure value, filtering, endpoint-resolution, route/cache, itinerary/revision, passive-actual and distance-forecast contracts. Required-SOC conversion remains unimplemented and must be added behind explicit vehicle/consumption policy rather than guessed.
- The calendar adapter now accepts an injected provider-specific online-event
  classifier, but no concrete provider mapping exists. The synthetic smoke
  pipeline must inject an explicit fake policy; real mappings require separate
  reviewed tests and must not infer from private event text by hidden convention.
- C3 term matching is intentionally a literal case-insensitive substring contract, not regex, tokenization or location-text matching. Any broader rule language requires a separately tested and documented checkpoint.
- C5 cache storage is an in-memory contract fake only. Persistent profile-scoped cache storage, privacy-key generation/rotation and migration behavior remain deferred to a later lifecycle/persistence checkpoint; no key material is logged or persisted by the domain.
- C8c/P2 define serialization and the Home Assistant `Store` adapter, but not retention pruning, transactional recovery UI or migration beyond schema version 1. No pre-version-1 payload exists; future schema changes require explicit forward migration and rollback tests.
- C8d–C8f and P1–P3 define orchestration, durable state, calendar normalization,
  fail-closed runtime composition, a passive sensor-platform adapter, diagnostics
  adapter and config-entry forwarding/unload lifecycle, but not the composed
  calendar-to-forecast source, a Home Assistant `DataUpdateCoordinator`, concrete
  aggregate diagnostics source, update interval or timeout/retry policy. Those
  policies must be explicit in later slices rather than silently defaulted here.
- P4 demonstrates deterministic contract composition only. Its fixed clock,
  synthetic location-text mapping, revision identifier, filter/forecast policies
  and route responses are fixtures, not production choices. Runtime windowing,
  real location resolution, revision-id generation and refresh scheduling remain
  unimplemented.
- A separate privacy-safe logging policy remains unimplemented; diagnostics safety does not make arbitrary logs safe.
- C8b metadata intentionally omits documentation/issue URLs and code-owner handles.
  A private GitHub remote now exists, but no public support URL or approved
  maintainer handle has been selected; these remain publication-readiness blockers.
- Ruff lint and formatting cover the complete repository. Strict Pyright now also covers the lifecycle module through minimal isolated Home Assistant contracts; other adapters, real-HA tests and dynamic fixtures remain outside that boundary. Expansion must add reviewed contract types rather than weakening strict mode or conflating installed runtime types with the dependency-free check.
- The development and real-HA requirements pin direct tool versions but not hashes or every transitive dependency. The real-HA harness pin currently requires Home Assistant 2026.8.1 exactly, and its test asserts that installed version. Action commits are immutable; a later supply-chain audit may add a fully hashed lock when a supported dependency workflow is chosen.
- C4 defines required freshness/accuracy/horizon fields but intentionally supplies no product defaults. Config-flow representation, default selection and migration policy remain future product work and must be reviewed before introduction.
- Location candidates currently cover passive vehicle GPS and already-resolved event/zone coordinates. Geocoding and Home Assistant zone/entity adapters remain outside the pure C4 boundary and are deferred to source composition.
- Config-entry schema version 1 minor version 2 and storage schema version 1 now
  exist. The 1.1-to-1.2 migration safely marks legacy entries unconfigured, but a
  reconfiguration/repair flow is still required before those entries can use the
  future composed source; options and later migrations remain unbuilt.
- An isolated disposable Home Assistant 2026.8.1 test environment now covers only
  the config flow. Real config-entry lifecycle, platform forwarding, entity
  registration/state-machine behavior and unload still lack real-HA tests.
- Private `origin` is configured and authorized for checkpoint pushes; repository
  visibility/settings and external publication remain out of scope.
- No real route-provider credentials or calls are permitted during unattended work.
- Exact Home Assistant entity selections and personal data are deliberately absent from the repository.

## Nightly runtime

- Hard deadline: 2026-08-26 03:01 CEST.
- OpenAI session and weekly usage are queried through Hermes' read-only account-usage implementation.
- Safety floor: stop/pause at 15% remaining; do not redeem the banked reset.
- Morning report scheduled for 08:00 CEST.
