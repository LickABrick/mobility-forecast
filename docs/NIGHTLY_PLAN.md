# Nightly phase-1 plan

Execution window: 2026-08-25 22:01–2026-08-26 03:01 CEST. Status report: 08:00 CEST.

The controller executes one bounded checkpoint per agent run and checks OpenAI Codex account windows between and during runs. Work stops or pauses when either remaining usage approaches the safety floor.

## Checkpoints

- [x] **C0 — Repository governance and safety foundation**
  - Local git repository, Apache-2.0 intent, Conventional Commits, agent rules, checkpoint validator, usage guard and status document.
- [x] **C1 — Product scope, architecture and ADRs**
  - V1/non-goals, one-entry-per-profile, clean-room decision, advisory-only policy, dynamic vehicle-location policy and provider architecture.
  - Evidence: `docs/PRODUCT_SCOPE.md`, `docs/ARCHITECTURE.md` and accepted ADRs 0001–0005; documentation/link/checkpoint validation passed on 2026-08-25.
- [x] **C2 — Domain contracts and package foundation**
  - Typed pure-Python event, location, route, vehicle, trip, quality and forecast models; package/tool configuration; unit-test foundation.
  - Evidence: nine deterministic `unittest` cases cover immutability, privacy-safe representations, temporal/numeric validation, degraded trips and forecast uncertainty; checkpoint validation passed on 2026-08-25.
- [x] **C3 — Calendar filtering and preview semantics**
  - Deterministic include/exclude rules, online/all-day/location handling, privacy-safe preview counts and tests.
  - Evidence: explicit immutable policy and decisions, stable exclusion precedence, aggregate-only previews and seven deterministic tests; checkpoint validation passed on 2026-08-26.
- [x] **C4 — Location resolution and freshness/fallback semantics**
  - Independent start/end policies, zone/GPS/future-day behavior, unknown accuracy, stale/unavailable fallbacks and tests.
  - Evidence: required threshold fields with no numeric defaults, inclusive passive-GPS gates, event/zone destinations, explicit partial fallback and unavailable results, privacy-safe reason codes and nine deterministic tests; checkpoint validation passed on 2026-08-26.
- [x] **C5 — Route provider and cache contracts**
  - Provider protocol, typed errors, deterministic fake, directional routes, cache key/TTL/privacy behavior and tests. No live API calls.
  - Evidence: asynchronous provider/cache protocols, five typed failure categories, exact deterministic fakes, directional HMAC-SHA-256 cache keys, explicit fresh/stale limits and refresh/fallback behavior; eight deterministic tests and checkpoint validation passed on 2026-08-26.
- [x] **C6 — Itinerary and planning revisions**
  - Chronological stops, multi-calendar dedupe, daily chaining, partial quality, immutable plan revisions and tests.
  - Evidence: explicit cross-calendar deduplication keys with conflict rejection, deterministic chronological stops, directional daily chaining, degraded legs, and append-only immutable revisions; seven deterministic tests and checkpoint validation passed on 2026-08-26.
- [x] **C7 — Passive actuals and robust forecast baseline**
  - Odometer sample quality, pending day closure, cold start, robust correction/outlier behavior, P50/P90 and tests.
  - Evidence: passive sample freshness gates, immutable revision-bound pending/actual records, rollback/daily-distance rejection, bounded median/nearest-rank correction and explicit cold start; ten deterministic tests and checkpoint validation passed on 2026-08-26.
- [x] **C8 — Home Assistant integration skeleton**
  - Manifest, HACS metadata, config-flow contract, coordinator boundary, read-only entities, translations and diagnostics redaction. No production installation.
  - [x] **C8a — Privacy-safe diagnostics projection**: a frozen typed aggregate snapshot and versioned JSON-safe allowlist exclude profile names, entity/event identifiers, event text, addresses, coordinates, provider details and credentials by construction; three deterministic tests and checkpoint validation passed on 2026-08-26.
  - [x] **C8b — Metadata and config-flow contract**: minimal manifest/HACS metadata, English config-flow strings and schema-version-1 user flow create independent, empty profile entries from one required name without behavioral defaults; four isolated contract tests and checkpoint validation passed on 2026-08-26.
  - [x] **C8c — Profile storage contract**: config-entry-scoped keys, immutable state, schema-version-1 JSON serialization and fail-closed decoding preserve plan revisions, pending days and actuals; five deterministic round-trip/integrity tests and checkpoint validation passed on 2026-08-26.
  - [x] **C8d — Profile coordinator boundary**: typed read-only source and config-entry-scoped storage protocols, immutable ordered forecast snapshots, persist-before-publish refresh semantics and failure isolation; six deterministic tests and checkpoint validation passed on 2026-08-26.
  - [x] **C8e — Read-only forecast distance sensor**: one entry-scoped passive sensor projects the earliest immutable forecast's P90 distance, bounded safe attributes and explicit unavailable values; five isolated adapter/translation tests and checkpoint validation passed on 2026-08-26.
  - [x] **C8f — Home Assistant diagnostics adapter**: an entry-scoped typed runtime boundary supplies only the existing aggregate snapshot to Home Assistant diagnostics; config-entry metadata/data/options are never traversed, source failures propagate, and two adapter tests plus the 75-test suite and checkpoint validation passed on 2026-08-26.
- [x] **C9 — CI, quality audit and handoff**
  - Ruff/pytest/type/config validation, GitHub Actions definitions, documentation consistency audit, remaining risks and phase-2 implementation backlog.
  - [x] **C9a — Deterministic CI definitions**: a least-privilege, timeout-bounded quality workflow pins action commits and Python tool versions, runs checkpoint/config validation and all 77 tests, lints the integration package, and strictly type-checks the dependency-free domain/coordinator/storage core; two contract tests and all configured checks passed locally on 2026-08-26.
  - [x] **C9b — Repository quality audit and handoff**: CI now lints and format-checks the complete repository; all 33 initial Ruff findings were resolved without behavior changes, the explicit strict-Pyright boundary has a contract test, Home Assistant/HACS JSON and translation contracts pass isolated tests, and all configured checks plus 78 tests passed locally on 2026-08-26. A broad strict-Pyright probe remains intentionally non-gating because absent Home Assistant types and dynamic contract fixtures produce 104 findings; lifecycle work must introduce isolated typed fixtures rather than production dependencies.

Phase 1 is complete. The next bounded post-phase checkpoint is the real
`async_setup_entry`/`async_unload_entry` lifecycle and sensor-platform forwarding,
proved only with isolated Home Assistant contract fixtures.

## Checkpoint definition of done

- Scope is coherent and no unrelated changes are included.
- Tests or deterministic validation cover the new contract.
- `python scripts/check_checkpoint.py` succeeds.
- Relevant configuration and schema/version documentation are reviewed.
- `docs/PROJECT_STATUS.md` records commands, results, decisions and residual risks.
- Commit follows Conventional Commits.
- Worktree is clean after commit, unless a blocker is explicitly documented.
