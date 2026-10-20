# Forecast algorithm

1. Validate ordered physical odometer states. Reject negative/non-finite values, decreases and intervals exceeding 240 km/h average (2 km telemetry tolerance). A legitimate 1,500 km journey over a day is accepted. Deduplicate by timestamp with live/raw states preferred over statistics.
2. Split bracketed intervals at timezone-aware local midnights, allocating distance proportionally to elapsed UTC seconds. Midnight-to-midnight brackets or fully contained brackets with essentially full coverage are observed. Allocated cross-day intervals are estimated. Intervals over 14 days do not support daily inference. Missing brackets remain unknown.
3. Require seven days with at least 90% bracket coverage. Estimated days can establish an overall provisional baseline, but cannot establish weekday precision. Last 365 days influence the model.
4. A hurdle estimator separates observed driving probability (positive days / eligible days) from distance conditional on driving. Parked days never lower the positive-distance outlier reference. With five or more positive observations, only an isolated tail (at most 5%, minimum one sample) above max(3 × positive 80th percentile, positive 80th percentile + 50 km) is capped. Repeated high-distance use remains intact. With fewer samples there is insufficient evidence to call a trip exceptional; uncertainty remains high.
5. At 28 precise days, weekday estimates with at least three samples shrink toward the global baseline with four pseudo-observations. At 56 useful days, recent 28-day robust average adjusts expectations by a factor bounded to [0.5, 1.5]. Sustained change affects both center and trend. At 112 precise days the most recent 56 precise observations supply weekday samples, so obsolete parked patterns do not permanently dominate. Unknown days are never driving-frequency samples.
6. Merge calendar plans by max, not sum. Incomplete route legs are lower bounds and widen uncertainty. No residual travel is invented. History must support a forecast even when calendars exist.
7. Today is never below the minimum from within-day measured intervals. A missing midnight state means this is a minimum, not exact total driven.
8. Rolling horizons use remaining fraction today, N-1 complete days and elapsed fraction of final day. Day fractions use actual UTC elapsed time through local DST boundaries. Annual uses 365 historical daily baselines, excluding calendar overlays.

Indicative daily ranges use empirical population standard deviation, a 15% baseline minimum, sample-count inflation and estimated-coverage inflation. They are not calibrated confidence percentages. Ranges are currently internal only. Variability from exceptional trips can widen ranges even while robust point estimates stay stable.

A bounded 90-date snapshot map stores the first supported daily forecast and compares it with later precise observed daily totals. Diagnostics give count, MAE and bias; zero evaluated samples does not imply measured accuracy. These metrics are developmental rather than a calibrated accuracy claim.

Retention and approximations are deliberate. There is no statistical UI questionnaire, external AI, or reconstruction of individual GPS trips.

## Daily evening reporting

Exact midnight brackets remain the strongest weekday evidence. At least fourteen near-daily raw intervals (20–28 elapsed hours, consecutive local dates, both reports between 16:00 and 23:59 with hours differing by at most one) provide weaker evidence: the delta is attributed to the ending report date with weight 0.5. This is a heuristic for after-trip telemetry, not proof of when travel occurred. Daily totals retain their `estimated` classification and interval allocation; only weekday inference uses that attribution. Weight controls shrinkage and minimum support. Multi-day gaps and statistics never receive this evidence. Unknown days remain unknown. Tests cover UTC, Amsterdam/New York DST and midnight/evening reporting.

## Genuine prediction history

A native local-time callback at 23:55 refreshes the model and captures tomorrow's
full-day prediction. The callback rechecks wall time after the refresh: a delayed
callback cannot capture a prediction after midnight. Each target date is immutable.
An offline/missed callback leaves a missing prediction; startup does not backfill.
Records contain target date, distance, capture time, lead seconds, quality/status,
calendar inclusion, origin, validity and record schema. Ready/provisional models
qualify; learning/unavailable snapshots are not strict evaluation predictions.
Records are retained for approximately 365 days. Legacy numeric snapshots retain
their value with origin `legacy`, unknown capture time and `valid: false`.

Completed local days use `daily_distances()`. Observed/estimated values with at
least 90% coverage may be displayed; only observed values enter strict metrics.
Unknown/partial coverage stays null, including days with no measurements. Today's
unfinished mileage is excluded. Estimated days have a distinct chart series.
Difference is **actual minus predicted**. MAE and signed bias, matched predicted
and actual totals, aggregate percentage error, evaluated count and exclusion
counts are available for 7/30/90 days. Exclusion counts can overlap. Zero actual
totals have null percentage error. Example: predictions 42/55 and observed 48/51
give MAE 5 km, bias +1 km, totals 97/99 km and aggregate error +2.02%. Synthetic
backtesting remains separate from these installed-instance snapshots.

## Optional EV charging forecast

See [EV setup, assumptions, provider limits and native dashboard](ev.md). EV is
disabled by default and never controls the vehicle or charger. Existing mileage
entities, history and calendar synchronization remain independent.

## Restart and EV remediation update

Complete calendar distance overlays are now stored separately from Waze route
cache entries. Startup restores validated, configuration-compatible plans before
the first forecast calculation, for up to two hours since agenda verification.
Stored records contain hashed fingerprints/config identity, dates, distances and
verification/routing times, not addresses or stops. Old storage needs no migration.
Restored data is labeled cached pending asynchronous verification. EV timing must
be rebuilt from the agenda; a numeric restored overlay is not a timed itinerary.
Failed startup retrieval uses 10/30/60/120-second retries then normal 30-minute
checks, rather than treating failure as successful retrieval. Routing identity
excludes unrelated EV options.

EV demand now reconciles full forecast distance with timed legs and measured
minimum movement today; remaining mileage is explicitly unallocated estimated
demand. Its day-end debit remains a coarse assumption, not exact travel timing.
Home windows preserve both sides of away intervals. Postcode-free Dutch addresses
require exact street, house number and municipality/locality. NDW ambiguous power
units remain fail-closed; no new evidence justifies automatic watts conversion.
Discovery progresses through ten unique destinations per pass, retaining completed
results and bounding temporary-failure retries. Revision tracking prevents old EV
calculations from publishing after inputs change. Response horizons filter windows
and demand while explicitly retaining a seven-day internal calculation horizon.

Validation evidence: reconstructed-store HA entry reload reproduces 95 km before,
95 km while calendar fetch is blocked after reload, and 95 km after verification.
This is in-process HA testing, not a real HA process restart. The 30/150/300
fixtures now process all destinations across bounded passes rather than starving
entries after the first ten. Full suite: 218 passed. The full requested restart,
race, session and DST matrices are not yet covered; multi-session scheduling,
coarse-day timing and provider semantics remain supervised-test limitations.
