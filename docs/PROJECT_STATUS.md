# Project status

Last updated: 2026-08-25 22:14 CEST

## Current phase

Phase 1 — architecture, contracts and safe development foundation.

## Completed

- C0 established the local repository, safety/privacy governance, Apache-2.0 intent, Conventional Commits and deterministic checkpoint tooling.
- C1 defined the V1 outcome and non-goals in `docs/PRODUCT_SCOPE.md`.
- C1 documented profile isolation, pure-domain boundaries, passive endpoint resolution, provider-neutral routing, immutable revisions and explicit quality semantics in `docs/ARCHITECTURE.md`.
- ADRs 0001–0005 record clean-room/HACS-first delivery, one-entry-per-profile, advisory-only V1, passive dynamic vehicle location and typed provider-neutral routing.

## Active checkpoint

C2 — Domain contracts and package foundation.

Next bounded checkpoint: add package/tool configuration and a tested pure-Python foundation for the typed event, location, route, vehicle, trip, quality and forecast contracts. Introduce only contracts with a concrete use; do not implement filtering, resolution or live adapters early.

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

C1 changes documentation and decisions only, so no executable behavior was introduced and behavior-level TDD was not applicable. The complete diff contains no credentials, personal event/location values or external calls.

Configuration review for C1: the repository does not yet contain `pyproject.toml`, Home Assistant manifest/HACS/string/translation files, workflows, config-flow schemas or storage schemas. `.gitignore`, package inclusion expectations and test configuration were reviewed; no change was justified. C1 establishes no numeric threshold, schema version or configuration default. Those contracts remain explicit work for their implementation checkpoints.

## Current decisions

- Name/domain: Mobility Forecast / `mobility_forecast`.
- License/delivery: Apache-2.0 clean-room implementation, HACS-first.
- Config model: one isolated config entry per forecast profile; multiple entries supported.
- V1 is read-only/advisory and excludes notifications, price/solar optimization and every physical action.
- Start and end locations use independent policies. Dynamic vehicle location is passive, freshness/quality gated and fallback based; no wake or refresh request is allowed.
- The domain uses provider-neutral typed boundaries. Google Routes is the intended first production route adapter; unattended tests use deterministic fakes only.
- Route and input failures remain partial, stale or unavailable and never become zero distance or false readiness.
- Historical plan revisions are immutable so later calendar edits do not rewrite training truth.

## Remaining risks and deferred details

- C2 must choose the minimum typed model without turning the architecture responsibilities into speculative abstractions.
- Numeric freshness thresholds, future-trip horizon, unknown accuracy and fallback precedence are deliberately deferred to tested C4 configuration.
- Route cache keys, TTL, stale behavior and provider error mapping are deliberately deferred to C5.
- Storage/config-entry schema versions, migrations and diagnostics redaction implementation remain unbuilt.
- No production Home Assistant mount or isolated HA development environment is configured.
- No GitHub remote/authentication is available; work remains local.
- No real route-provider credentials or calls are permitted during unattended work.
- Exact Home Assistant entity selections and personal data are deliberately absent from the repository.

## Nightly runtime

- Hard deadline: 2026-08-26 03:01 CEST.
- OpenAI session and weekly usage are queried through Hermes' read-only account-usage implementation.
- Safety floor: stop/pause at 15% remaining; do not redeem the banked reset.
- Morning report scheduled for 08:00 CEST.
