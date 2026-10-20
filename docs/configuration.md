# Configuration reference

## Vehicle

Initial setup asks **Vehicle name / Voertuignaam** (optional) and **Odometer sensor /
Kilometerstandsensor** (required). Use a numeric lifetime cumulative source in km/mi.
**Vehicle** options change the name. **Reconfigure** changes the source while retaining
history and entity identities; discontinuous replacements are rejected, not rebased.

## Options navigation

- Vehicle
- Calendars and routes
- Known locations
- Electric vehicle
  - EV setup
  - Additional vehicle data (when enabled)
  - Advanced charging preferences (when enabled)
  - Back to vehicle settings

Forms merge their own fields into existing options. Disabling EV retains its inputs;
calendar changes retain known locations and history. Optional entities can be cleared.

## Calendars and routes

| Setting | Default | Effect |
| --- | --- | --- |
| Calendars / Agenda's | None | Calendar entities used for planned journeys |
| Use Waze for routes | Off | Sends locations to external routing; requires Waze integration |
| Ignore nested appointments / Geneste afspraken negeren | Off | Excludes fully contained sub-events, including potentially genuine journeys |
| Region | Explicit selection | Existing identifiers retained; changing region separates cache identity |

See [calendar setup](calendar-routing.md#setup), [Waze](calendar-routing.md#waze) and
[known locations](calendar-routing.md#known-locations). Aliases map labels to full
addresses/coordinates. Editing one does not delete unrelated cached routes.

## Electric vehicle

See [EV setup](ev-charging.md#setup), [advanced options](ev-charging.md#advanced-options)
and [vehicle entities](ev-charging.md#vehicle-entities). EV is off initially.

| Setting | Default | Consequence |
| --- | --- | --- |
| Battery percentage sensor | None | Must report %; unknown values withhold advice |
| Usable capacity, consumption, vehicle AC power | None | User must supply physical vehicle values |
| Preferred charging limit / Gewenste laadlimiet | 80% | Normal target ceiling, not power |
| Minimum reserve / Minimale reserve | 15% | Preferred battery remaining after travel |
| Charging mode | Home only | Home only, home and appointments, or appointments only |
| External lookup consent | Off | Required for public charging destination queries |
| Minimum appointment duration | 90 min | Hard eligibility filter for public opportunities |
| Maximum charger distance | 300 m | Straight-line radius, not walking distance |
| Session overhead | 15 min | Deducted connecting/disconnecting time |
| Prefer longer sessions | On | Soft preference, never overrides reachability/reserve |
| Home window | 18:00–07:00 | Overnight windows supported; assumed availability |
| Allow higher targets | Off | Explicit permission for exceptional journey targets |
| Absolute maximum | 100% | Exceptional target ceiling; vehicle limit still applies |

Minimum useful charging energy defaults to 5 kWh. It is a soft ranking preference,
not a hard safety constraint; necessary smaller sessions remain possible.

## Visibility and source recovery

Five forecast sensors register even while learning; disabled registry entries stay
disabled. Mileage timeline is disabled by default. Repeated decreases on distinct
UTC dates trigger a resetting-counter Repair and withhold forecasts. A single decrease
is rejected as a possible glitch. State class alone does not prove source suitability.

## Testing without a connected car

Create a Number helper with unit km, range 0–1000000 and a starting value of 10000.
Expose it through a Template sensor with device class Distance and state class Total
increasing. Increase after simulated journeys; never reset daily. This tests source
behavior, not instant historical backfill. Remove the demo vehicle before using real
history. See [staging validation](developer/staging-validation.md).

## Manual sync

Manual Sync / Handmatige synchronisatie queues an immediate bounded cycle and returns
off automatically. User-off does not cancel it. It refreshes current inputs, requests
calendar verification and optional EV work, while reusing caches and provider cooldowns.
Repeated requests coalesce; a total 120-second manual deadline bounds waiting.

Attributes: `status`, `last_triggered_at`, `last_started_at`, `last_finished_at` and
sanitized `last_error_code`. Success means the cycle completed, not all routes or
providers succeeded. Check calendar and EV status independently.

```yaml
action: mobility_forecast.sync_now
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
```

Unlike the nonblocking switch, this action waits and raises on failure. Obtain the
entry ID with the action's native vehicle selector. See [action contracts](developer/actions.md).
