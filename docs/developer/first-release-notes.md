# First public release notes

Use the following content to finalize **both** the release PR's `CHANGELOG.md` entry
and the matching version section in its PR description. This is a deliberate,
one-time editorial step **after the last Release Please update**, not a replacement
for version generation. Retain the generated PR wrapper, title, branch and labels.

```markdown
## 1.0.0

Initial public release of Mobility Forecast for Home Assistant.

### Included

- Five mileage forecast sensors based on local odometer history.
- Calendar-aware routing with optional Waze travel estimates and known locations.
- Historical comparison of forecasts with recorded mileage.
- Manual synchronization and read-only actions for history, forecasts and EV advice.
- Optional Mileage Timeline and native dashboard examples.
- Native Home Assistant setup/options with English and Dutch guidance and local branding.
- Optional, experimental EV charging estimates for home and appointment charging.

### Setup

Install as a HACS custom repository or copy the integration manually, restart Home
Assistant, then add Mobility Forecast under Settings → Devices & services. Follow
https://github.com/LickABrick/mobility-forecast/blob/main/docs/setup.md and replace
sample entity IDs in dashboard examples with your actual vehicle entities.

### Important limitations

- EV advice is experimental and informational; it does not control a vehicle or charger.
- Public lookup is optional and requires consent; ambiguous provider data is rejected.
- Short EV horizons filter the existing plan rather than independently optimizing it.
- Forecast quality depends on available odometer history, calendar data and routing.
- The forecast action defaults to 30 local dates; Mileage Timeline retains 31 rows.
```

Add only validation claims supported by completed staging. Do not imply real vehicle,
HAOS upgrade or provider acceptance tests were performed merely because CI passed.
Optionally retain generated user-relevant fixes below this summary; omit the invalid
`v1.0.0...v1.0.0` link and stale Unreleased/bootstrap text from the final release entry.

**Overwrite warning:** Release Please regenerates the version section and PR body on
subsequent preparation runs. Freeze ordinary main merges, wait for preparation to finish,
then finalize both copies. Commit only the changelog edit to the generated PR using the
normal GitHub edit/commit interface (no force push or history rewrite), update its
PR description, and wait for `tests`, `hassfest`, `hacs` again before merging. If
preparation runs again, repeat editorial review; do not assume edits survived.
Publication uses the merged PR's notes, so changing only CHANGELOG.md is insufficient.
Future releases do not need this first-release template.
