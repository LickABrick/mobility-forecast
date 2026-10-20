# Getting Started

## Installation

Follow [README installation](../README.md#installation). HACS custom repository
installation and manual copying both require an HA restart after installation or
replacement. Back up before upgrades; do not remove private storage to update.

## Odometer

Add Mobility Forecast from Settings → Devices & services. Choose a numeric lifetime
vehicle odometer in km/mi; range, trip and daily distance sensors are not suitable.
An optional vehicle name controls the device title. Repeat for another vehicle.
Recorder must retain observations for the selected source. Purged history cannot
be recovered from nothing; suitable physical-state statistics may supplement it.

## First forecast

Open the vehicle device. Five distance sensors appear immediately, even while
unknown: today, tomorrow, next seven days, next thirty days and annual expectation.
History imports in the background. Open **Forecast status** for import status and usable history days. Seven adequately covered completed
days establish a baseline; weekday patterns need more evidence. Unknown is not zero.

Regular readings, including unchanged observations while parked, improve coverage.
A stale unchanged state is not proof of zero travel. If the source is excluded from
Recorder, enable recording and allow history to accumulate.

## Dashboard

Use the native [Entities card example](dashboard.md). Find actual entity IDs in the
vehicle device page or Developer Tools → States; names in examples are placeholders.
Mileage Timeline is enabled by default; existing integration-default-disabled entries
are enabled on reload, but user-disabled entries remain disabled. Genuine predicted
versus actual history requires pre-day snapshots; nothing is backfilled.

## Optional setup

Calendars are not required. See [calendar setup](calendar-routing.md#setup) for Waze
and locations. EV is disabled initially; see [EV setup](ev-charging.md#setup).

## Manual synchronization

Turn on Manual Sync to queue bounded background work. It returns off when finished.
The waiting `sync_now` action reports errors rather than treating failures as success.
Watch **Sync status** for phase and last result, **Last successful sync** for the last
fully successful manual job, and **Calendar status** for route progress. Partial work
is not success. See [sync diagnostics](sync-diagnostics.md). Automatic refresh continues.

## Next steps

Read [configuration](configuration.md) before changing sources; retained history is
preserved but discontinuous odometers are not silently merged. For unexpected values,
start with [troubleshooting](troubleshooting.md).
