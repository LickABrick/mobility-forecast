# Local validation and remaining release gates

Executed locally on Python 3.13.5 / Home Assistant Core 2026.2.3:

- pytest: 43 tests passing, including native config/duplicate flow, actual in-process HA integration setup/five sensors/unload (mocked recorder), Store round trip/removal, recorder/statistics adapter mocks, deterministic forecasts/DST, route cache/error mocks, conservative merging and calendar normalization.
- Ruff lint and formatting checks.
- Mypy on pure models/odometer/forecasting modules only, not the entire HA adapter layer.
- Offline manifest/HACS metadata/translation leaf-key parity validation.
- Editable package installation smoke test.

Not executed: live Waze requests, production HA server/browser UI, current 2026.10 runtime, upstream Hassfest and HACS hosted validators. CI jobs are provided but have not been run on GitHub. Offline checks are not equivalent to those validators.

The master specification's exhaustive edge-case test matrix is not fully covered by these 43 tests. In particular multi-vehicle reload interaction, all source-transition permutations, unsupported-schema migrations, calendar options/reconfigure UI paths and recorder statistics variants need broader integration tests before treating this as a fully certified release.

Remaining scope differences: compact combined options screen rather than separate vehicle/calendar menus; only simple alias object editor; internal uncertainty/evaluation rather than optional diagnostic entities; no automatic source counter rebasing; periodic calendar fetch rather than event push subscriptions; registry renames resolve on reload; source-unit discontinuity is guarded by converted values but unit metadata is not separately persisted. Intra-day actual versus remaining distance is not exposed as separate entities. Calendar missing/ambiguous locations share an incomplete itinerary status. No calibrated confidence or accuracy claims are made.

All ten requested phase commits exist, but commit presence does not mean every master-prompt acceptance item has been certified. See README for actual behavior and limitations. No remote push/publication has been performed.
