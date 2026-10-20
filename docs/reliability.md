# Reliability remediation — 2026-10-20

## Evidence and boundaries

Starting branch: master at 1529e74015691d59f32ce8ed8fe7d68b100f07ff, clean.
The setuptools failure was reproduced before changes. Explicit namespace package
inclusion fixes editable/wheel installation without deleting branding assets.
Pillow is now explicitly a test dependency. No manifest runtime requirements,
entity identities, configuration schema or storage version were changed.

### Reconstructed Store / HA entry reload measurements

Deterministic frozen clock; 95 km calendar overlay before unload. Calendar retrieval
is blocked during first publication. These are simulated HA entry reloads with
aged persisted records, not real process downtime.

| Verification age | First forecast | After unchanged verification |
|---|---:|---:|
| Ordinary reload | 95 km | 95 km |
| 5 minutes | 95 km | 95 km |
| 3 hours | 95 km, provisional | 95 km |
| 8 hours | 95 km, provisional | 95 km |
| 24 hours exactly | 95 km, provisional | 95 km |
| 25 hours | historical baseline (35–37 km fixture) | 95 km |

Manual sync is triggered while retrieval is blocked and preserves that first
value. Existing authoritative-cancellation tests remove the overlay; outage tests
retain within 24 hours and expire beyond it. No freshness timestamp is advanced
merely by restoration. No private stop data is persisted.

## Conservative EV behavior

Timed legs and unallocated daily mileage are separate. A 180 km forecast with
30 km timed routes leaves 150 km untimed, not a fabricated journey. If this demand
risks reserve, precise advice is withheld. Already-below-reserve energy can support
an immediate useful session or a physically reachable charger with an explicit
reserve warning. Uncertain extra demand combined with an existing reserve violation
also withholds a precise target. The scheduler remains a small first-action
heuristic, not a proven multi-session optimizer.

Home windows subtract complete away chains and retain intermediate returns.
Current not-home evidence requires a known return before assuming charging.
Unknown location still uses labeled assumed home availability. Real itinerary
origin/destination hashes are used; no coordinate identities are persisted anew.

Shortened action responses deliberately withhold seven-day recommendations and
assessment status. This loses some convenient advice but avoids claiming a target
or shortfall belongs to a different horizon. No extra providers are called.

## Audit findings and remaining acceptance gaps

The final source review removed alternatives/shortfall after an insufficient-data
override, preventing a confident alternative surviving rejected primary advice.
Discovery stops obsolete revisions after awaited provider work, preserves reusable
results, suppresses unchanged publications, and permits another bounded retry burst
after a day instead of permanently exhausting attempts.

NDW contract evidence is in [ndw-contract.md](ndw-contract.md). Unit ambiguity and
public-access semantics are unresolved external limitations. No guessed conversion.
Current fresh power is used for active home charging estimates; time-to-target
with unknown target semantics is not used. No controls are issued.

Not all requested acceptance combinations have dedicated tests: full two-vehicle
HA lifecycle with different EV configurations, every below-reserve limit/session
combination, exhaustive DST home-window permutations, real network revision races,
and detailed memory/task/storage/Recorder metrics remain gaps. Type checking now
includes 14 modules but unannotated function bodies are not strict typing coverage.
Brand structure/transparency/path tests pass; no GitHub browser or real HA process
restart was performed. No production EV session was tested. These are explicit
limitations, not production certification.
