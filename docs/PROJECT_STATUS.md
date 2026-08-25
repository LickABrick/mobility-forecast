# Project status

Last updated: 2026-08-25 22:11 CEST

## Current phase

Phase 1 — architecture, contracts and safe development foundation.

## Completed

- Phase-0 reuse audit concluded that Mobility Forecast should be a clean-room project, not a permanent fork.
- Local repository initialized with safety, privacy and git-governance rules.
- Initial V1 boundaries and unattended nightly checkpoints recorded.

## Active checkpoint

C1 — Product scope, architecture and ADRs.

## Verification evidence

C0 verification on 2026-08-25:

```text
python3 -m compileall -q scripts                  PASS
python3 scripts/check_checkpoint.py               PASS
scripts/codex_usage.py via Hermes Python           PASS
Apache-2.0 system license copy                     present
```

The usage endpoint returned only plan/window percentages and reset times; no credential material was printed or stored. The initial checkpoint is committed before autonomous C1 work starts.

## Current decisions

- Name/domain: Mobility Forecast / `mobility_forecast`.
- License: Apache-2.0.
- Publication direction: HACS-first; keep future Core-quality compatibility in mind.
- Config model: one config entry per forecast profile; multiple entries supported.
- First production route-provider direction: Google Routes behind a provider-neutral protocol; unattended work uses only fakes.
- V1 is read-only/advisory and excludes energy-price/solar optimization and physical actions.
- Vehicle location is passive, freshness-gated and fallback-based; no wake/refresh requests.

## Known constraints

- No production Home Assistant mount or isolated HA development environment has been configured yet.
- No GitHub remote/authentication is available; all nightly work remains local.
- No real route-provider credentials or calls are permitted during unattended work.
- Exact Home Assistant entity selections and user data are deliberately absent from the repository.

## Nightly runtime

- Hard deadline: 2026-08-26 03:01 CEST.
- OpenAI session and weekly usage are queried through Hermes' read-only account-usage implementation.
- Safety floor: stop/pause at 15% remaining; do not redeem the banked reset.
- Morning report scheduled for 08:00 CEST.
