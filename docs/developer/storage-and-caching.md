# Storage and caching

Each vehicle owns a version-1 HA Store. Four-column physical readings, structured
prediction snapshots, hashed routes, validated calendar distances and optional EV
provider cache share atomic debounced persistence. No recorder database is written.
Corrupt/unsupported storage stops writes and raises a Repair instead of overwriting.

Physical history retains three years with first/last readings per UTC hour. Route
cache holds 512 directed entries for seven days. Calendar verification freshness is
two hours; identity-compatible complete distance plans may remain provisional up to
24 hours, including reload. Cancellation removes plans immediately. Restored numeric
plans contain no trusted EV stops. EV provider caches are bounded and hash keyed.

Never silently migrate or discard history. Add fixtures for older supported payloads;
new optional records must reject corrupt content independently. Removing one vehicle
deletes only its integration-owned store. Unload flushes/cancels owned work. Backups
remain sensitive despite hashed keys: known locations and mileage reveal patterns.

See [architecture](architecture.md) for ownership, cache identity and concurrency.
