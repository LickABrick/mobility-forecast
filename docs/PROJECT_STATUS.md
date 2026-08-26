# Project status

Last updated: 2026-08-26 02:27 CEST

## Current phase

Phase 1 — architecture, contracts and safe development foundation.

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

## Active checkpoint

C5 — Route provider and cache contracts.

Next bounded checkpoint: use TDD to define the provider-neutral route protocol, typed failures, deterministic fake and directional privacy-safe cache behavior. Use synthetic endpoints only and make no live route calls.

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

## Remaining risks and deferred details

- C2–C4 now define value, filtering and endpoint-resolution contracts, but not provider failure/cache protocols, itinerary assembly or forecast algorithms; those remain C5–C7 work.
- Calendar adapters must eventually normalize provider-specific online-event signals into the required `is_online` flag; adapter mapping and config-entry representation remain deferred to C8.
- C3 term matching is intentionally a literal case-insensitive substring contract, not regex, tokenization or location-text matching. Any broader rule language requires a separately tested and documented checkpoint.
- Route currently models only a successful positive route. Typed provider failures and deterministic fake-provider behavior remain explicitly deferred to C5.
- Domain representations reduce accidental disclosure but do not replace the dedicated diagnostics/log redaction boundary and tests required at C8.
- Python 3.13 compatibility is explicit, but CI has not yet exercised Ruff or Pyright because those tools and workflows are deferred to C9.
- C4 defines required freshness/accuracy/horizon fields but intentionally supplies no product defaults. Config-flow representation, default selection and migration policy remain C8 work.
- Location candidates currently cover passive vehicle GPS and already-resolved event/zone coordinates. Geocoding and Home Assistant zone/entity adapters remain outside the pure C4 boundary and are deferred.
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
