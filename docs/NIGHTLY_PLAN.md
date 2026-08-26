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
- [ ] **C4 — Location resolution and freshness/fallback semantics**
  - Independent start/end policies, zone/GPS/future-day behavior, unknown accuracy, stale/unavailable fallbacks and tests.
- [ ] **C5 — Route provider and cache contracts**
  - Provider protocol, typed errors, deterministic fake, directional routes, cache key/TTL/privacy behavior and tests. No live API calls.
- [ ] **C6 — Itinerary and planning revisions**
  - Chronological stops, multi-calendar dedupe, daily chaining, partial quality, immutable plan revisions and tests.
- [ ] **C7 — Passive actuals and robust forecast baseline**
  - Odometer sample quality, pending day closure, cold start, robust correction/outlier behavior, P50/P90 and tests.
- [ ] **C8 — Home Assistant integration skeleton**
  - Manifest, HACS metadata, config-flow contract, coordinator boundary, read-only entities, translations and diagnostics redaction. No production installation.
- [ ] **C9 — CI, quality audit and handoff**
  - Ruff/pytest/type/config validation, GitHub Actions definitions, documentation consistency audit, remaining risks and phase-2 implementation backlog.

## Checkpoint definition of done

- Scope is coherent and no unrelated changes are included.
- Tests or deterministic validation cover the new contract.
- `python scripts/check_checkpoint.py` succeeds.
- Relevant configuration and schema/version documentation are reviewed.
- `docs/PROJECT_STATUS.md` records commands, results, decisions and residual risks.
- Commit follows Conventional Commits.
- Worktree is clean after commit, unless a blocker is explicitly documented.
