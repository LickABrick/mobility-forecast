# Agent instructions — Mobility Forecast

These rules apply to every automated or human-assisted change in this repository.

## Safety boundary

- Work only inside this repository unless a read-only upstream/documentation lookup is required.
- Never install into or modify production Home Assistant.
- Never call real vehicle, charging, climate, lock, plug, light or notification services.
- Never wake a vehicle or request an active vehicle refresh.
- Never use or commit real addresses, calendar contents, GPS coordinates, entity-state dumps, API keys, tokens or credentials.
- Never push, publish, create a remote, issue, PR or release without explicit user approval.
- External route-provider calls require explicit test credentials and are forbidden during unattended work; use deterministic fixtures/fakes.

## Product boundary

- Project name: `Mobility Forecast`; integration domain: `mobility_forecast`.
- License: Apache-2.0; implementation is clean-room. Smart EV Trip Planner may be cited as prior art but no GPL source may be copied.
- HACS-first, while following current Home Assistant quality rules where practical.
- One Home Assistant config entry represents one forecast profile; multiple entries must be supported.
- V1 is read-only/advisory: calendars, filters, location resolution, route-provider abstraction, passive odometer learning, uncertainty-aware distance/SOC advice.
- Price/solar optimization and physical actions are explicitly out of V1.

## Architecture rules

- Keep domain logic independent from Home Assistant wherever possible.
- Depend on typed protocols at boundaries: calendar source, location resolver, route provider, vehicle source, storage and forecast model.
- Treat start and end location as independent policies.
- Route failures must never become zero distance or “charging not needed”. Represent complete, partial, stale and unavailable states explicitly.
- Preserve historical plan revisions; later calendar edits must not rewrite training truth.
- Diagnostics and logs must redact event text, addresses and coordinates.
- Do not add speculative abstractions without at least one concrete use and tests.

## Git workflow

- Branch `main` must remain buildable. Checkpoint work commits directly to `main`;
  pushing to the authorized private `origin` requires explicit user approval and
  successful verification.
- Use Conventional Commits: `type(scope): imperative summary`.
- Allowed types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `build`.
- Keep subjects under 72 characters; explain rationale and compatibility impact in the body when non-trivial.
- One commit must represent one coherent change. Do not bundle unrelated docs, architecture and implementation work.
- Do not accumulate the entire phase into one commit. Prefer a checkpoint commit after each verified vertical slice.
- Never amend, squash, rebase, force-push or rewrite an earlier checkpoint during unattended work.
- Do not commit generated caches, runtime logs, secrets, personal data or failing experiments.
- Before each commit: inspect `git diff`, run `python scripts/check_checkpoint.py`, run the most specific relevant tests, and run the full available suite when practical.
- After each commit: verify `git status --short --branch`, update `docs/PROJECT_STATUS.md` and the checklist in `docs/NIGHTLY_PLAN.md` as part of that same checkpoint, then inspect the new commit.
- If verification fails, fix it before committing. If blocked, leave a documented blocker and a clean or clearly explained worktree.

## Development discipline

1. Read `docs/NIGHTLY_PLAN.md` and `docs/PROJECT_STATUS.md` before changing files.
2. Select the highest-priority ready checkpoint; do not start several unrelated checkpoints.
3. Define or update tests before implementation when behavior is clear.
4. Make the smallest coherent change.
5. Run real verification and record exact results in `docs/PROJECT_STATUS.md`.
6. Commit using Conventional Commits.
7. Stop after the assigned checkpoint so usage can be measured before more work begins.

## Configuration checkpoints

At every checkpoint review and, when needed, update all applicable configuration:

- `pyproject.toml` and tool versions;
- `custom_components/mobility_forecast/manifest.json`;
- `hacs.json`;
- translation/string files;
- GitHub Actions workflows;
- `.gitignore`, package inclusion and test configuration;
- config-flow schema and storage schema versions;
- documentation that describes defaults or compatibility.

Configuration changes require validation and tests. Never silently change a default or schema.
