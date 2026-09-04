# Testing Mobility Forecast on Home Assistant 2026.8.1

The public repository can be installed as a HACS custom integration from
`https://github.com/LickABrick/mobility-forecast`. HACS installs the default
branch (`main`) because the repository has no releases, and `hacs.json` declares
Home Assistant 2026.8.1 as the minimum supported version. The manually built
`mobility_forecast-0.0.0.zip` remains available as a checked fallback.

## Safety and current limitations

- This integration is **pre-alpha and read-only**. It has no vehicle wake, climate,
  charging, lock, plug, notification, or other physical-service path.
- The current package reads selected calendars immediately and every 15 minutes,
  classifies reviewed standalone meeting URLs locally, applies the profile's explicit
  structural policy, resolves included physical locations and routes daily itineraries
  for configured hosted/self-hosted OpenRouteService, Geoapify or Google profiles.
- Production provider calls use the explicitly configured credentials/endpoints.
  Automated verification intercepts the managed HTTP session with deterministic
  responses and never calls an external provider.
- Raw event text and location text are not persisted or exposed by the sensor.
  Calendar and zone entity IDs stay in the profile config entry. Resolved coordinates
  and route results may be cached. A private profile-scoped cache stores them under
  opaque HMAC keys for only the configured retention periods; they are never exposed
  by the sensor or diagnostics.
- Test the automated compatibility target, Home Assistant **2026.8.1**. Stop if the
  backup fails, files already exist unexpectedly, or startup logs contain an
  exception. The manual ZIP path also requires a valid checksum.

## Install or update from public `main` through HACS

1. Make the Home Assistant backup in section 1 before downloading anything.
2. In the HACS dashboard, open the top-right 3-dot menu and select **Custom
   repositories**. Enter `https://github.com/LickABrick/mobility-forecast`, select
   category **Integration**, and select **Add**.
3. Open Mobility Forecast in HACS and select **Download**. There are no releases;
   HACS therefore installs the public repository's default branch, `main`. If a
   version selector is shown, choose the default branch rather than an old commit.
4. For a later checkpoint, first use **Update information** to refresh repository
   metadata, then open the repository's 3-dot menu and select **Redownload**.
   Updating information alone does not replace downloaded files. With no releases,
   HACS identifies versions by the first seven characters of the `main` commit.
5. Confirm HACS shows **Pending restart**, then restart Home Assistant fully.
   Reloading the config entry alone does not reload custom-integration Python modules.
6. Continue with the log and config-flow checks below.

Do not mix a HACS installation with manual ZIP extraction. Remove or back up the
whole existing integration directory before switching installation methods.

## Hosted OpenRouteService test profile

The recommended simple path uses one free user-supplied HeiGIT/OpenRouteService API
key. Create or review the key at `https://account.heigit.org/`; never paste it into
an issue, log excerpt, screenshot, calendar, or this repository. The integration sends
that same key as the documented `api_key` query parameter to hosted Pelias and as the
`Authorization` header to hosted ORS routing. The disclosed recipients are:

- calendar location text goes to the hosted Pelias geocoder at
  `https://api.heigit.org/pelias/v1/search`;
- the resulting start/destination coordinates go to hosted routing at
  `https://api.heigit.org/openrouteservice/v2/directions/driving-car`.

Self-hosted ORS does not bundle geocoding. The fields **Self-hosted ORS routing base
URL**, **Self-hosted geocoder family**, and **Self-hosted geocoder base URL** are not
part of this hosted test and must remain empty. No request or credential falls back
to a self-hosted endpoint, Geoapify, Google, or another geocoder.

Use these conservative values for this checkpoint's manual smoke test. They are
explicit test choices, not integration defaults:

| Home Assistant field | Test choice |
| --- | --- |
| Calendars | One disposable calendar with synthetic events |
| Start anchor / End anchor | Explicitly selected HA zones; each is independent |
| Physical events | Include |
| Online events | Exclude |
| All-day events | Exclude |
| Events without a location | Exclude |
| Routing and geocoding provider family | OpenRouteService hosted (recommended) |
| Hosted provider API key | The tester's HeiGIT/OpenRouteService key |
| Location-data consent | I understand and consent |
| Maximum geocode requests per refresh | 4 |
| Maximum route requests per refresh | 8 |
| Maximum attempts per request | 2 |
| Timeout per attempt | 10 seconds |
| Geocode cache retention | 24 hours |
| Fresh route cache age | 6 hours |
| Maximum stale route cache age | 24 hours |
| Tolls | Avoid |
| Highways | Allow |
| Minimum history samples | 5 |
| Minimum / maximum correction | 60% / 180% |
| Cold-start conservative estimate | 125% |

Every choice selector starts on **Select explicitly**; leaving that placeholder in
place fails closed. A submitted valid profile loads immediately. If its selected
calendar already contains an included future physical event, that initial refresh
can send the event location and route coordinates to the two recipients above.
Create the API key and synthetic calendar before submitting the form.

## Build the artifact from this checkout

From the repository root:

```sh
/usr/bin/python3 scripts/build_test_zip.py
/usr/bin/python3 scripts/build_test_zip.py --check dist/mobility_forecast-0.0.0.zip
```

The build writes these two ignored artifacts:

```text
dist/mobility_forecast-0.0.0.zip
dist/mobility_forecast-0.0.0.zip.sha256
```

The script packages only tracked files below
`custom_components/mobility_forecast`, fixes timestamps and modes, emits a
SHA-256 checksum, and checks archive names, bytes, metadata, and scope against the
checkout. Keep the ZIP and checksum sidecar together.

## 1. Back up Home Assistant

1. In Home Assistant, open **Settings > System > Backups**.
2. Create a manual backup that includes Home Assistant configuration. Give it a
   recognizable pre-test name.
3. Wait for the backup to finish successfully and download a copy off the Home
   Assistant host.
4. Confirm Home Assistant reports version 2026.8.1 under **Settings > About**.
5. Check whether `/config/custom_components/mobility_forecast` already exists.
   Do not overwrite it. If it is an intentional earlier test copy, stop Home
   Assistant and move that whole directory to a safe backup location first.

Home Assistant backup documentation:
https://www.home-assistant.io/common-tasks/general/#backups

## 2. Verify the package

Transfer both artifact files to the same temporary directory on the Home
Assistant host (or verify them before transfer). In that directory run:

```sh
sha256sum --check mobility_forecast-0.0.0.zip.sha256
unzip -l mobility_forecast-0.0.0.zip
```

The checksum command must report `OK`. Every archive member must start with
`custom_components/mobility_forecast/`. The list must not contain `.storage`,
`.env`, `secrets.yaml`, credentials, runtime data, `__pycache__`, tests, or
repository documentation. Do not install a package that fails either check.

## 3. Install the files

Use a Home Assistant file-transfer method you already trust, such as the SSH,
Samba, or Studio Code Server app. Preserve the archive paths and extract the ZIP
into the Home Assistant configuration root, normally `/config`:

```sh
cd /config
test ! -e custom_components/mobility_forecast
unzip /path/to/mobility_forecast-0.0.0.zip -d /config
```

The `test` command must succeed silently; if it does not, stop instead of
mixing versions. After extraction, verify at least these paths exist:

```text
/config/custom_components/mobility_forecast/__init__.py
/config/custom_components/mobility_forecast/manifest.json
/config/custom_components/mobility_forecast/strings.json
/config/custom_components/mobility_forecast/translations/en.json
```

Do not copy the repository's tests, `.nightly`, `.git`, credentials, or runtime
files into Home Assistant.

Home Assistant's developer documentation defines custom integrations under
`<config directory>/custom_components/<domain>`:
https://developers.home-assistant.io/docs/creating_integration_file_structure/

## 4. Restart and check logs

1. Restart Home Assistant from **Settings > System > Restart Home Assistant** (the
   restart action may be under the power menu, depending on the frontend layout).
2. Wait until the frontend reconnects and startup completes.
3. Open **Settings > System > Logs** and search for `mobility_forecast` and
   `Mobility Forecast`.
4. Expected result: no import error, manifest error, config-flow error, setup
   traceback, or repeated retry loop. A configured OpenRouteService, Geoapify or
   Google profile may make bounded geocoding and routing requests during its immediate
   refresh; it never makes a vehicle or physical-service request.
5. If there is an exception, copy only the relevant redacted traceback for the
   test report. Do not include calendar event text, addresses, coordinates,
   tokens, or full entity/state dumps.

Do not continue to config flow if Home Assistant does not return cleanly.

## 5. Run the config-flow smoke test

1. Open **Settings > Devices & services**.
2. Select **Add integration**, search for **Mobility Forecast**, and open it.
3. Enter a non-sensitive test profile name, for example `Synthetic commute`.
4. Select one or more calendars. Use a disposable Local Calendar containing only
   synthetic events. To test routing, add one future physical event with a
   non-sensitive public-place location chosen by the tester; do not record that
   location in an issue or test report. Calendar order is retained per profile.
5. Complete every field exactly as listed under **Hosted OpenRouteService test
   profile**. Select the start/end zones independently, leave all three self-hosted
   fields empty, paste the one hosted API key only into **Hosted provider API key**,
   and explicitly select **I understand and consent**.
6. Submit the form. Submission creates and loads one config entry, schedules a
   15-minute refresh, and runs the first refresh immediately. With an included
   located event, expect one Pelias geocode followed by one ORS route unless a fresh
   cache entry already exists.
7. Expected result: the Mobility Forecast config entry is loaded and exposes exactly
   the sensor described below.
8. To change an installed profile, open its integration entry and select
   **Reconfigure**. Current non-secret calendars, anchors and policies are suggested;
   the API key is deliberately not suggested and must be entered again. Calendar
   selection can be changed. Submitting reloads the profile and can immediately call
   the selected provider under the new explicit configuration.
9. Optionally repeat with another synthetic profile to confirm profiles are
   independent. This is not required for the minimum smoke test.

Failure indicators are a missing integration, a form that cannot list calendar
entities, an entry stuck in setup/retry, or a traceback in the logs.

## 6. Verify the expected entity state

Open the created Mobility Forecast entry and its entities. It should expose one
read-only sensor named **Forecast distance** (Home Assistant may derive the exact
entity ID from the profile/device naming context).

Expected states are deliberately distinct:

```text
No included future physical event:
State: unknown
Unit: km
Forecast attributes: absent

Included event, but geocode/route is rejected, unavailable or incomplete:
State: unknown
Unit: km
Quality: partial or unavailable
Distance: never zero

Calendar/anchor/storage refresh itself fails:
State: unavailable
Unit: km

Complete hosted Pelias + ORS route:
State: positive conservative P90 road distance
Unit: km
Attributes: service_date, distance_p50_km, quality, generated_at
```

The entity must not expose calendar text, addresses, coordinates, calendar entity
IDs, route-provider data, or credentials. No Mobility Forecast service, button,
switch, or action entity should exist. HTTP 401/403, quota, timeout, malformed body
and transport failures fail closed without consuming provider response bodies or
putting credentials/private request values in integration logs. A provider failure
can therefore appear as `unknown` without a traceback; it must not become a cached
zero or trigger a request to any other provider.

After checking the entity, inspect **Settings > System > Logs** once more for new
`mobility_forecast` exceptions. Record the Home Assistant version, ZIP SHA-256,
config-entry load result, entity state, and any redacted error. Do not export full
states or diagnostics containing unrelated Home Assistant data.

## 7. Uninstall or roll back

Normal HACS uninstall:

1. In **Settings > Devices & services**, open each Mobility Forecast config entry
   and delete it. This removes config-entry data; removing only repository files does
   not.
2. Restart Home Assistant and confirm the entries are gone.
3. In **HACS > Mobility Forecast > 3 dots > Remove**, remove the downloaded
   repository. HACS deletes the managed integration directory but not related data.
4. Restart Home Assistant again, check the logs, and confirm Mobility Forecast is no
   longer listed under **Add integration**.

Manual-install rollback:

1. Delete every Mobility Forecast config entry and restart as above.
2. Stop Home Assistant before deleting files.
3. Remove only `/config/custom_components/mobility_forecast`.
4. If an earlier integration directory was moved aside, restore that whole
   directory now; otherwise leave the path absent.
5. Start Home Assistant, check the logs, and confirm Mobility Forecast is no
   longer listed.

The current artifact performs read-only local calendar refreshes and may create routed
plan revisions through the selected OpenRouteService, Geoapify or Google provider. Do
not hand-edit Home Assistant's `.storage` files. If startup, config entries, or unrelated
state do not return to the pre-test condition, use Home Assistant's supported backup
restore flow with the backup created in step 1 instead of manually modifying internal
storage.
