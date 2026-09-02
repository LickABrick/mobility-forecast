# ADR 0005: Isolate route providers behind a typed protocol

- Status: Superseded in part by [ADR 0006](0006-explicit-provider-selection.md)
- Date: 2026-08-25

## Context

Road distance is provider-dependent and route calls can fail, expire, be rate-limited or reveal sensitive locations. Coupling planning directly to one provider would make domain behavior hard to test and future adapters expensive.

## Decision

The domain depends on a typed provider-neutral route protocol. Directional requests and results retain route-affecting inputs, provenance, age and explicit success/failure quality. A missing or failed route is never represented as zero distance.

Google Routes is the intended first production adapter, but no Google type enters the domain model. Tests and unattended work use deterministic fakes and synthetic locations only. Cache key, TTL, stale-result and privacy rules will be specified in C5 before implementation.

## Consequences

- Calendar, itinerary and forecast logic are provider-independent.
- Provider adapters translate authentication, quotas, errors and response shapes at the boundary.
- A-to-B and B-to-A routes are distinct.
- Real route calls require later explicit authorization and dedicated test credentials; they are not part of unattended verification.
