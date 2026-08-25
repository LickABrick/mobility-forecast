# ADR 0004: Resolve dynamic vehicle location passively

- Status: Accepted
- Date: 2026-08-25

## Context

A vehicle may not be at a fixed home origin when a trip starts. Using its location can improve near-term route estimates, but stale tracking data can be misleading and requesting a refresh can wake the vehicle. Destinations have different evidence and fallback needs from origins.

## Decision

Resolve every start and end location independently. A start policy may select a passively observed vehicle location only when it is appropriate to the trip horizon and meets explicit freshness and quality requirements. The resolver never requests an update.

When that sample is unsuitable, the result records fallback provenance and uses the configured start fallback if available; otherwise it is unavailable. An unresolved end location does not fall back to the current vehicle location merely because that location exists.

C4 will define and test threshold fields, horizon behavior, unknown accuracy and fallback precedence. This decision intentionally establishes no numeric default.

## Consequences

- Vehicle source protocols cannot expose wake or refresh commands.
- Location results need provenance, observation time and quality/failure state.
- Current position can improve near-term plans without becoming an unsafe universal origin.
- Partial/unavailable routes remain visible when either endpoint cannot be resolved.
