# ADR 0002: Represent one forecast profile per config entry

- Status: Accepted
- Date: 2026-08-25

## Context

Users may need independent planning for multiple vehicles, people or calendar sets. A single global integration configuration would mix lifecycle, history, credentials and failure state, while one config entry per low-level source would fragment a coherent forecast.

## Decision

One Home Assistant config entry represents one complete forecast profile. Multiple entries are supported. Each entry is an independent composition root with its own selected calendars, filtering, endpoint policies, route-provider configuration, passive vehicle sources, storage namespace, coordinator and entities.

Mutable caches, revisions and model state are profile-scoped. Cross-profile aggregation, if ever needed, must be a separate read-only concern rather than shared planning state.

## Consequences

- Reloading or failing one profile does not affect another.
- Config flow and storage keys must be entry-scoped and migration-safe.
- The same underlying Home Assistant entity may be explicitly selected by more than one profile without making profiles share state.
- Tests must exercise at least two entries to detect accidental global state.
