# NDW contract verification — 2026-10-20

Retrieved the official consumer documentation and its linked
`dafne_api_geojson.yaml` at:
https://docs.ndw.nu/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/

The schema explicitly describes `power_max` as **Maximum power in kW for this
availability**. It lists AC1, AC2, AC2_SPLIT, AC3 and DC; there is no per-record unit
field. The documented GeoJSON endpoint and bbox format match our adapter.

A live bbox request to the implemented endpoint (`5.10,52.08,5.13,52.10`)
returned 195 features. An AC3 / IEC_62196_T2 connector reported `power_max: 15000.0`.
This confirms the specification/live discrepancy still exists. It does **not**
establish a reliable rule for converting every large number from watts.

No automatic conversion is implemented. Values outside plausible documented AC
kW remain rejected. A malformed/ambiguous connector no longer prevents another
valid connector on the same feature from being considered. Occupancy over five
minutes is unknown; location data is accepted up to one day. Future availability
is always a potential opportunity, never guaranteed. The schema's `open` flag
alone also does not prove unrestricted public access. Production compatibility
remains limited pending provider clarification. No private customer address was
used in this check; no raw response is committed.
