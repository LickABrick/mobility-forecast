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
History imports in the background. Inspect `history_import_status`, `history_days`
and `forecast_status` in Developer Tools → States. Seven adequately covered completed
days establish a baseline; weekday patterns need more evidence. Unknown is not zero.

Regular readings, including unchanged observations while parked, improve coverage.
A stale unchanged state is not proof of zero travel. If the source is excluded from
Recorder, enable recording and allow history to accumulate.

## Dashboard

Use the native [Entities card example](dashboard.md). Find actual entity IDs in the
vehicle device page or Developer Tools → States; names in examples are placeholders.
Enable Mileage timeline explicitly only when you need comparison attributes.

## Optional setup

Calendars are not required. See [calendar setup](calendar-routing.md#setup) for Waze
and locations. EV is disabled initially; see [EV setup](ev-charging.md#setup).

## Manual synchronization

Turn on Manual Sync to queue bounded background work. It returns off when finished.
The waiting `sync_now` action reports errors rather than treating failures as success.
See [manual sync](configuration.md#manual-sync). Normal automatic refresh continues.

## Next steps

Read [configuration](configuration.md) before changing sources; retained history is
preserved but discontinuous odometers are not silently merged. For unexpected values,
start with [troubleshooting](troubleshooting.md).
