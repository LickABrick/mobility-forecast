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
