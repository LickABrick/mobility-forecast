# Architecture

Each config entry is one vehicle and owns a typed `VehicleCoordinator` in `runtime_data`. No mutable vehicle globals exist.

- `config_flow`: single-screen source selection, options and source reconfiguration.
- `odometer`: source semantics, unit conversion and finite-value validation.
- `history`: recorder executor imports, source overlap normalization, ordered continuity and daily interval aggregation.
- `storage`: version-1 HA Store per entry, atomic delayed writes and unload flush. Corrupt data is not overwritten. Removal deletes only this store.
- `forecasting` / `models`: deterministic ordinary Python domain logic.
- `calendar_manager` / `locations`: bounded native calendar action and conservative location normalization; no event titles persist.
- `routing`: small provider protocol, Waze response adapter, bounded cache and plausible trip chains.
- `sensor`: five coordinator entities with stable entry-based unique IDs and localized names.
- `diagnostics`: privacy-minimal counts, feature status and evaluation.

Live changes debounce recalculation for 60 seconds; periodic refresh is 30 minutes. Chronological live readings append/replace hourly endpoints without whole-history sorting. History import compacts first/last physical readings per UTC hour, retaining three-year coverage independently of report rate; raw database reads are six-hour batches. Schema v1 four-column rows remain compatible; old files are read in full, validated and compacted idempotently, never sliced to the latest N rows.

Calendar work is an entry-owned background task, outside the historical-state lock. A 45-second whole-refresh budget covers event retrieval plus routing; three fixed workers process independent daily chains. Identical in-flight legs share a future. Configuration generations reject obsolete results; unload cancels/awaits work. Completion requests a forecast refresh; odometer updates publish immediately without external waits. Failed refreshes clear stale overlays and expose routing_unavailable while preserving historical predictions. Refresh attempts are coalesced and spaced at least 30 minutes. Imports execute in the recorder executor and merge against current memory, preserving intervening live updates. Entries own their background import and listeners. Unload cancels pending work, flushes state and shuts down the coordinator.

Forecast computation is inexpensive and bounded by retained readings/365 forecast days. Calendar queries cover at most 30 upcoming days. Waze uses metric units, selects the fastest valid alternative, and never substitutes failed requests with zero distance. Hash-keyed cache identity includes provider/region/preferences/origin/destination.

No recorder database is written. Supported sources are states and semantically suitable state statistics; `sum` is not a mileage value. Reconfiguration preserves entity identity and rejects clearly discontinuous history.

## Entity startup contract

Sensor forwarding precedes asynchronous initialization. The coordinator starts with an initializing forecast containing five null values; sensors explicitly remain available while the forecast is unknown or in error. Unique IDs remain `<entry_id>_<forecast_key>`, device identity remains `<domain>,<entry_id>`. Explicit user-disabled registry entries are respected, never forcibly re-enabled. Initialization and import tasks belong to the config entry; shutdown cancels initialization before other work and never flushes an unloaded empty store over disk. Import failure leaves registered entities and existing history intact.

Recorder planning uses the supported `history.state_changes_during_period` function with ascending `limit=1` and no start-state lookup to find the first retained change for this entity. Detailed six-hour reads start there; statistics remain in 90-day batches. There is no direct database-table query or assumed retention setting. Short raw brackets (up to two hours) supersede statistics, not the global raw min/max extent. Monotonic/speed validation still applies to merged physical states.
