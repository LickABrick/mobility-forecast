# Troubleshooting

- **Mostly parked vehicles:** confirmed zero days count toward driving probability; recurring weekend or weekly travel is not discarded as an outlier. Missing telemetry is not a confirmed zero. Compare several weeks, not one unexpected journey.
- **Slow routing:** historical forecasts publish independently. Agenda processing has a 45-second overall deadline and retries no faster than the scheduled refresh. routing_unavailable means historical fallback, not zero-distance journeys.
- **Odometer selector:** displays distance-class sensors or sensors in km/mi. Incomplete device-class metadata is supported through the unit fallback. Final validation still rejects trip/range counters.
- **Learning / unknown predictions:** wait for seven adequately bracketed days or verify recorder has retained this odometer. No updates is not evidence of a parked car.
- **Source unavailable:** history remains stored. Check original integration, unit and numeric value. After seven days without valid measurements predictions become unknown instead of indefinitely fresh-looking values.
- **Source rejected:** range/trip sensors are unsuitable. Use lifetime cumulative mileage, preferably a distance sensor with total state class.
- **Counter decrease / replacement:** data is rejected to avoid negative trips. Restore a continuous source. Start a new vehicle entry only if deliberately discarding the model is appropriate.
- **No calendar contribution:** verify calendars, routing opt-in, Waze action and region. Generic names need a known location/zone. Online, all-day, crossing-midnight or impossible overlapping itineraries may not yield routes.
- **Routing unavailable:** historical forecasts remain valid. Provider errors are not zero-distance journeys. Requests retry on later refresh and usable cached routes remain until expiration.
- **Storage repair:** unreadable state is preserved, not overwritten. Restore a backup or remove/re-add the vehicle to start fresh. There is no safe automatic interpretation of arbitrary corrupt files.

For bug reports provide integration version, HA version, sanitized downloaded diagnostics and reproduction steps. Do not attach private calendar content, addresses, coordinates, storage files or authentication details publicly.

## Five sensors missing from States

1. Open Settings → Devices & services → Mobility Forecast. Check whether the entry is loaded, disabled, retrying or **Failed to set up**.
2. Open the vehicle device → Entities. Enable any user-disabled sensors. Search the actual entity IDs in Developer Tools → States (names/IDs may have been renamed).
3. Registered enabled entities should have a state even with no history: `unknown`, not absent. Inspect `forecast_status`, `history_days`, `history_import_status`, `calendar_status`.
4. Check Settings → System → Logs for `custom_components.mobility_forecast`, platform `sensor`, config entry setup and entity-registration errors. Enable integration debug logging temporarily if needed, then disable it.
5. If still missing, provide HA Core version, integration version/installed commit, entry load status, entity registry disabled status and startup traceback. Redact locations, vehicle identifiers and calendar details. Do not delete the entry/history to troubleshoot.

The production missing-entity report was not reproduced in the in-process HA tests. Startup was hardened against initialization blocking registration, but no specific cause in that installation has been confirmed.

`history_import_status`: pending/importing/complete/failed/incompatible_source. `forecast_status`: initializing/learning/provisional/ready/source_unavailable/source_incompatible/error. Resetting counters raise Repairs; select a lifetime vehicle odometer via Reconfigure. Calendar `routing_unavailable` is historical fallback, not failure of the five sensors.
