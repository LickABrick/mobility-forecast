# Reproducible performance and backtesting

Commands: `.venv314/bin/python -m scripts.backtest` and `.venv314/bin/python -m scripts.benchmark_history`.

Rolling-origin synthetic backtest: 84-day initial training; cutoffs advance seven days through day 238; 7/30-day horizons. Same weekday/shrinkage/trend pipeline, replacing only the old/new global estimator. Deterministic profiles, not measured real-world accuracy.

| Profile | Actual weekly km | Old final weekly | New final weekly | Old 7-day MAE | New 7-day MAE | Old 30-day MAE | New 30-day MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Weekend | 300 | 203.33 | 300 | 91.43 | 0 | 364.82 | 27.02 |
| Weekly | 250 | 168.33 | 250 | 77.24 | 0 | 308.52 | 22.52 |
| Daily | 280 | 280 | 280 | 0 | 0 | 0 | 0 |
| Commuter | 260 | 260 | 260 | 0 | 0 | 8.11 | 8.11 |
| Variable | 400 | 353.33 | 400 | 44.14 | 0 | 159.44 | 29.73 |
| Low mileage | 15 | 11.67 | 15 | 3.15 | 0 | 12.16 | 1.35 |

Backtest CSV also reports signed bias and aggregate weekly/monthly errors. These repeated-week synthetic profiles demonstrate the defect and its correction; they do not establish calibrated predictive accuracy for arbitrary future trips. Thirty-day errors remain due to weekday shrinkage.

Three-year streaming compaction benchmark, Python 3.14.2, local Linux, tracemalloc enabled:

| Report interval | Input samples | Retained samples | Seconds | Peak Python MiB |
|---|---:|---:|---:|---:|
| 10 seconds | 9,460,801 | 52,561 | 101.880 | 9.25 |
| 1 minute | 1,576,801 | 52,561 | 22.240 | 9.25 |
| 1 hour | 26,281 | 26,281 | 0.201 | 4.62 |
| 3 days | 366 | 366 | 0.005 | 0.06 |

This measures compaction only, not recorder database query latency, HA import elapsed time or process RSS. Import bounds materialized raw responses to six hours (2160 readings at 10-second frequency), compacts after each batch, and retains O(hours of history), not O(raw reports). Current implementation still merges/sorts the bounded retained set per batch; import CPU/query overhead is not constant. Live chronological observations use an append/replace hourly fast path and persist on forecast debounce rather than copying the whole store for every event.

Compaction is conservative in fractional-offset timezones: removed interior samples can reduce precise daily evidence where local midnight falls within a UTC hour. It never invents exact daily values. Retained cumulative endpoints preserve interval totals. Sensor updates faster than ten seconds can still produce larger individual six-hour recorder responses; the upstream history API materializes its time window.

## Recorder query planning follow-up

Fixture measurements for a three-year initial window: one oldest-retained-change query plus 40 raw queries for ten retained days (41 total), 120 for thirty days (121 total), or one boundary query and zero raw queries for no history. Previously all profiles queried 4380 raw six-hour windows. Statistics queries are additional (up to thirteen 90-day windows for three years), unchanged. This is demonstrated API-call reduction, not a measured database elapsed-time speedup. Tests replace database execution at its boundary; real database query plans and import duration require beta observation. A sensor with three full years of raw retention can still need 4380 windows to bound materialized responses; no unsupported earliest-state database query is used.

## Progressive routing measurements

Deterministic in-process HA service tests, Python 3.14.2, synthetic 30-day calendars, mocked 1 ms latency per Waze service call (not live Waze):

| Appointments | Locations | Calls across cycles | First-cycle calls | Peak concurrent calls | Measured active test elapsed |
|---|---|---:|---:|---:|---:|
| 150 | distinct | 180 | 60 | 3 | 0.153 s |
| 300 | distinct | 330 | 60 | 3 | 0.277 s |
| 150 | same repeated | 2 | 2 | 1 | 0.011 s |
| 300 | same repeated | 2 | 2 | 1 | 0.012 s |

Elapsed excludes the production one-minute pauses: tests explicitly advance continuation eligibility. Distinct-location chains require N+30 unique directed legs; caching prevents repeated partial-chain calls between cycles. Previous code could attempt at most 60 calls and could not complete those distinct-location months in one refresh. This is improved completion behavior, not a reduction in inherently necessary distinct routes. For repeated locations the old cache could also achieve two calls; no speedup claimed there.

Nested maintenance example: strict mode makes zero calls because conflicts invalidate the day; filtering makes two calls for the valid parent round trip and no child calls. It is not valid to claim a six-to-two measured reduction from the old conservative planner. A deadline test completes the first three days then blocks subsequent requests: three plans survive, 27 remain pending, and active work is cancelled by the 100 ms test deadline. Production cycle deadline remains 45 seconds. Run `.venv314/bin/pytest tests/test_progressive_calendar.py -q -s` to reproduce; wall times vary.

## Intelligent cache follow-up

Python 3.14.2, mocked 1 ms service responses, 30-day repeated five-location schedule:

| Appointments | Lookups | Hits | Misses | Shared consumers | Waze calls | Complete/pending | Active test time |
|---|---:|---:|---:|---:|---:|---|---:|
| 150 | 180 | 54 | 6 | 120 | 6 | 30 / 0 | 0.049 s |
| 300 | 330 | 103 | 7 | 220 | 7 | 30 / 0 | 0.093 s |

Second cycles use zero Waze calls. Hit/shared splits depend on deterministic worker timing in this fixture; total calls and unique keys are asserted. Existing distinct-location progressive fixtures still require 180/330 calls, first-cycle <=60 and peak <=3; no inherent-route reduction is claimed. New owned-task lifecycle adds overhead: observed active scheduler times were 0.328/0.676 seconds in one run, not a performance speedup claim.

An explicit before/after experiment loaded the routing/location modules from baseline commit 6170e18 and compared the same schedule against current code. Exact five-location spellings: 6→6 calls (150) and 7→7 (300), confirming existing reuse rather than claiming it as new. Alternating unambiguously equivalent comma spacing: 12→6 and 14→7. These counts are measured with mocked responses, not live Waze. Replay fixtures: `.venv314/bin/pytest tests/test_cache_scenarios.py tests/test_progressive_calendar.py -q -s`. Baseline comparison can be reproduced by running the same five-location fixture with baseline modules and alternating `', '` and `' ,'` on odd days.

Nested tickets still trigger zero child calls: strict overlap mode rejects the day (zero Waze calls), optional filtering requests only the parent's two directed legs. Cache tests additionally verify atomic HA persistence/reconstruction, seven-day expiration, direction-specific values, region separation, alias updates, valid cache during outage and cancellation/recovery.
