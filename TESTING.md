# Testing Mobility Forecast on Home Assistant 2026.8.x

The public repository can be installed as a HACS custom integration from
`https://github.com/LickABrick/mobility-forecast`. The manually built
`mobility_forecast-0.0.0.zip` remains available as a checked fallback.

## Safety and current limitations

- This integration is **pre-alpha and read-only**. It has no vehicle wake, climate,
  charging, lock, plug, notification, or other physical-service path.
- The current package validates installation, config flow, lifecycle, persistence
  boundaries, and an unavailable sensor. Production calendar-to-route-to-forecast
  runtime composition is not implemented yet.
- The existing end-to-end forecast evidence uses only synthetic calendar data,
  synthetic locations, and a deterministic fake route provider in tests. Real
  route-provider and real forecast output are not part of this artifact.
- Selecting a calendar stores its entity ID in this profile. The current runtime
  does not schedule calendar reads or publish a forecast from it.
- Test only on Home Assistant **2026.8.x**. Stop if the backup fails, the checksum
  fails, files already exist unexpectedly, or startup logs contain an exception.

## Install or update from public `main` through HACS

1. Add `https://github.com/LickABrick/mobility-forecast` under **HACS > Custom
   repositories** with category **Integration**.
2. Open Mobility Forecast in HACS and select **Download**.
3. This pre-release repository does not have tagged releases yet and its manifest
   version is still `0.0.0`. After a fix on `main`, HACS may not show a normal
   version update badge; open the repository menu and use **Redownload** instead.
4. Restart Home Assistant fully after every download or redownload. Reloading the
   config entry alone does not reload custom-integration Python modules.
5. Continue with the log and config-flow checks below.

Do not mix a HACS installation with manual ZIP extraction. Remove or back up the
whole existing integration directory before switching installation methods.

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
4. Confirm Home Assistant reports a 2026.8.x version under **Settings > About**.
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
   traceback, or repeated retry loop. This package creates no polling task.
5. If there is an exception, copy only the relevant redacted traceback for the
   test report. Do not include calendar event text, addresses, coordinates,
   tokens, or full entity/state dumps.

Do not continue to config flow if Home Assistant does not return cleanly.

## 5. Run the config-flow smoke test

1. Open **Settings > Devices & services**.
2. Select **Add integration**, search for **Mobility Forecast**, and open it.
3. Enter a non-sensitive test profile name, for example `Synthetic commute`.
4. Select one or more calendars. Prefer a disposable Local Calendar containing
   only synthetic test events; an empty synthetic calendar is sufficient for this
   lifecycle checkpoint. Calendar order is retained per profile.
5. Submit the form.
6. Expected result: one new Mobility Forecast config entry is created and loads.
7. Optionally repeat with another synthetic profile to confirm profiles are
   independent. This is not required for the minimum smoke test.

Failure indicators are a missing integration, a form that cannot list calendar
entities, an entry stuck in setup/retry, or a traceback in the logs.

## 6. Verify the expected entity state

Open the created Mobility Forecast entry and its entities. It should expose one
read-only sensor named **Forecast distance** (Home Assistant may derive the exact
entity ID from the profile/device naming context).

For this package, the expected state is:

```text
State: unavailable
Unit: km
Forecast attributes: absent
```

`unavailable` is intentional and safer than a fabricated zero: runtime forecast
composition and refresh scheduling are not present. The entity must not expose
calendar text, addresses, coordinates, calendar entity IDs, route-provider data,
or credentials. No Mobility Forecast service, button, switch, or action entity
should exist.

After checking the entity, inspect **Settings > System > Logs** once more for new
`mobility_forecast` exceptions. Record the Home Assistant version, ZIP SHA-256,
config-entry load result, entity state, and any redacted error. Do not export full
states or diagnostics containing unrelated Home Assistant data.

## 7. Uninstall or roll back

Normal uninstall:

1. In **Settings > Devices & services**, open each Mobility Forecast config entry
   and delete it.
2. Restart Home Assistant and confirm the entries are gone.
3. Stop Home Assistant before deleting files.
4. Remove only `/config/custom_components/mobility_forecast`.
5. If an earlier integration directory was moved aside, restore that whole
   directory now; otherwise leave the path absent.
6. Start Home Assistant, check the logs, and confirm Mobility Forecast is no
   longer listed.

The current artifact does not trigger a refresh, so it should not create profile
forecast state. Do not hand-edit Home Assistant's `.storage` files. If startup,
config entries, or unrelated state do not return to the pre-test condition, use
Home Assistant's supported backup restore flow with the backup created in step 1
instead of manually modifying internal storage.
