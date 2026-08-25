# ADR 0003: Keep V1 advisory-only

- Status: Accepted
- Date: 2026-08-25

## Context

Forecasting from calendars, routes and passive vehicle observations is uncertain. Combining early forecast logic with physical control would enlarge the safety boundary and make failures consequential.

## Decision

V1 is read-only and advisory. It may read explicitly configured sources, persist integration-owned planning/model state and publish forecast entities, previews and redacted diagnostics. It must not call vehicle, charging, climate, lock, plug, light or notification services; wake or actively refresh a vehicle; or optimize charging against price or solar data.

Any later automation or charging optimizer consumes published forecast output across a separate boundary and requires its own decision record and safety analysis.

## Consequences

- Domain and adapter protocols expose observations, not command methods.
- Home Assistant V1 registers no physical-action or notification services.
- Missing inputs suppress or qualify advice instead of triggering corrective action.
- Charging optimization can evolve independently without coupling it to calendars, vehicles or route providers.
