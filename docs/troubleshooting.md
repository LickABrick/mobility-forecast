# Troubleshooting

- **Learning / unknown predictions:** wait for seven adequately bracketed days or verify recorder has retained this odometer. No updates is not evidence of a parked car.
- **Source unavailable:** history remains stored. Check original integration, unit and numeric value. After seven days without valid measurements predictions become unknown instead of indefinitely fresh-looking values.
- **Source rejected:** range/trip sensors are unsuitable. Use lifetime cumulative mileage, preferably a distance sensor with total state class.
- **Counter decrease / replacement:** data is rejected to avoid negative trips. Restore a continuous source. Start a new vehicle entry only if deliberately discarding the model is appropriate.
- **No calendar contribution:** verify calendars, routing opt-in, Waze action and region. Generic names need a known location/zone. Online, all-day, crossing-midnight or impossible overlapping itineraries may not yield routes.
- **Routing unavailable:** historical forecasts remain valid. Provider errors are not zero-distance journeys. Requests retry on later refresh and usable cached routes remain until expiration.
- **Storage repair:** unreadable state is preserved, not overwritten. Restore a backup or remove/re-add the vehicle to start fresh. There is no safe automatic interpretation of arbitrary corrupt files.

For bug reports provide integration version, HA version, sanitized downloaded diagnostics and reproduction steps. Do not attach private calendar content, addresses, coordinates, storage files or authentication details publicly.
