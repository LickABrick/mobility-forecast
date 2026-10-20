# Contributing to Mobility Forecast

Keep the integration local-first, bounded and usable without calendars or EV.
No automatic vehicle control, custom frontend, pricing engine or external database.
Discuss major scope changes in an issue before implementing them.

## Environment

Primary target: HA Core 2026.10.2, Python 3.14.2+. Install that Python first.

```bash
python3.14 -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
python -m pip check
pytest -q --cov=custom_components.mobility_forecast --cov-report=term-missing
ruff check .
ruff format --check .
mypy
python scripts/validate.py
python scripts/check_release.py
python scripts/check_docs.py
python -m pip wheel --no-deps --wheel-dir dist .
python scripts/check_wheel.py
```

Use a clean `dist/` before building (the wheel checker expects one wheel). Tooling
is test-only; brand generation additionally needs CairoSVG, fonttools and Pillow
and the attributed DejaVu font. HA must never install image tooling at runtime.

## Changes and tests

Use a short branch such as `fix/forecast-days` or `docs/setup`. Use Conventional
Commits: `fix:`, `feat:`, `docs:`, `ci:`, `chore:`; use `!` and an explanation for
breaking changes. Squash PR titles should follow the same convention. Explain
user-visible behavior and release-note implications, not only implementation.

Add focused regression tests for changed behavior, then run the complete checks.
External routing/geocoding/discovery stays mocked in mandatory CI. Provider fixtures
must be synthetic or sanitized, with source/schema/date documented. Verify provider
contracts against official documentation; do not infer ambiguous units from magnitude.

Preserve unique IDs, existing option keys, historical readings and storage schemas.
No silent migrations or resetting data to resolve errors. Test older payloads, reload,
unload, multiple entries and corrupt optional records when relevant. Mypy currently
covers selected domain modules, not strict whole-project typing.

Keep `strings.json`, `translations/en.json` and `translations/nl.json` key sets in
sync. English translations mirror source strings. Use native selectors and concise
field explanations; update task guides and old-path forwarders together.

Never commit HA storage, raw calendar payloads, home locations, vehicle identifiers,
credentials or private diagnostics. Avoid logging addresses even at debug level.

## Local HA and review

Use a disposable HAOS VM/spare instance and [staging checklist](docs/developer/staging-validation.md).
Mocked in-process HA tests are not graphical UX, actual restart or vehicle-session
certification. Report exactly what was tested. PRs should include motivation,
compatibility, tests, docs/translations and known limitations. Run Hassfest/HACS in
CI as well as local scripts. See [release process](docs/developer/release-process.md)
for versioning; do not manually bump three files independently.
