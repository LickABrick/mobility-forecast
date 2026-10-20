# Product polish review — 2026-10-20

## Baseline and scope

Started clean on master at `975e870b1b11cb6fa25a268289ba8a4ffbe77d89`.
Existing mileage/calendar/history/manual-sync/EV/storage functionality was present.
The missing pieces were product navigation, EV hierarchy/native controls, truthful
forecast day counts, local HA brand delivery and public maintenance/release tooling.
No forecasting engine, unique ID, storage schema or option-key redesign was needed.

## Implemented

- Concise product README, user/developer index, task guides and preserved baseline archive.
- Native EV submenu with enabled-only advanced/entity entries; merged options retain
  unrelated values. Number/time selectors, SoC filtering, clearer errors and translated
  field help use supported description placeholders (verified by Hassfest).
- Unambiguous available numeric same-device suggestions only for range/power/duration;
  other semantics stay manual. Existing choices and explicit clears suppress suggestions.
- Explicit forecast days now honored; action default is 30, display remains 31.
- Generated local icon/light/dark logos, plus wheel package-data regression checks.
- Contributor/security/templates/CODEOWNERS, weekly Dependabot, measured coverage floor,
  docs/YAML/anchor/release checks, controlled release preparation and manual publication.

## Validation and boundaries

Complete suite passed 281 tests after documentation regressions, up from 259 baseline.
Coverage measured 86.53% before the final two documentation tests, with an 85% CI floor.
Ruff, formatting, Mypy (14 selected modules), metadata/translation checks, documentation
checks, release consistency, editable install, pip check, wheel build/content checks,
Docker Hassfest (one integration, zero invalid), actionlint 1.7.12 all passed.
Local HACS stopped before validation because GITHUB_TOKEN is absent. Current official
HACS docs accept local brand/icon.png; brands ignore is removed, but this branch's
hosted run must confirm it. No push/release/live repository settings were performed.

Manual HAOS installation, graphical controls/branding, real process restarts, release
PR/updater execution and real vehicle sessions were not performed. Native EV setup
still shows all core values when disabled and consent on the same setup form: native
forms do not dynamically hide fields as mode selection changes. Advanced mode-specific
fields are filtered on entry. Waze identifiers remain unchanged, not guessed relabeled.
Same-device suggestions cannot establish arbitrary vehicle telemetry meaning; no
name-based or cross-device matching is used. No automatic optional sensor discovery
or control is promised. Full two-vehicle/DST/session/provider race matrices remain
incomplete. No new provider polling or expensive background work was added.

## Release recommendation

**Beta for the overall integration; optional EV remains experimental.** Strong mocked
and in-process coverage supports supervised deployment, not production certification.
Before the first public release: pass hosted HACS with brands check, run staging,
exercise Release Please's first PR and version updaters, configure protected branches,
release environment and credential, verify release notes/tag/HACS installation.
The metadata's 1.0.0 bootstrap is intentional existing versioning, not a stable-rating
claim. Review [maintainer setup](repository-setup.md) and [staging](staging-validation.md).

## Deferred refinements

Scheduled future-HA compatibility monitoring and external-link probes are not mandatory
CI: the pinned supported HA target remains authoritative. Third-party workflow actions
retain upstream version tags (HA/HACS rolling refs); immutable pinning is future
hardening, not claimed complete. No new Repairs or status codes were needed: symptom
and status documentation improves clarity without Recorder churn or compatibility risk.
Historical archive links retain their original source-relative context and are excluded
from evergreen link checks. Exact live branding API/visual verification remains staging.
