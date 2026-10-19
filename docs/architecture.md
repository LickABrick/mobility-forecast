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

Live changes debounce recalculation for 60 seconds; periodic refresh is 30 minutes. Imports execute in the recorder executor and merge against current memory, preserving intervening live updates. Entries own their background import and listeners. Unload cancels pending work, flushes state and shuts down the coordinator.

Forecast computation is inexpensive and bounded by retained readings/365 forecast days. Calendar queries cover at most 30 upcoming days. Waze uses metric units, selects the fastest valid alternative, and never substitutes failed requests with zero distance. Hash-keyed cache identity includes provider/region/preferences/origin/destination.

No recorder database is written. Supported sources are states and semantically suitable state statistics; `sum` is not a mileage value. Reconfiguration preserves entity identity and rejects clearly discontinuous history.
