# ADR 0001: Build a clean-room HACS-first integration

- Status: Accepted
- Date: 2026-08-25

## Context

Existing EV trip-planning projects demonstrate product demand, but source with an incompatible license cannot form the implementation basis for an Apache-2.0 integration. The project should be practical to install before pursuing stricter Home Assistant Core inclusion requirements.

## Decision

Mobility Forecast is an Apache-2.0 clean-room implementation. Prior projects may be cited as prior art, but their source is not copied or translated. Requirements are derived from independently written product and architecture documents and implemented against tests.

Distribution is HACS-first while following current Home Assistant quality practices where practical. HACS-first does not permit provider-specific or Home Assistant concerns to enter the pure domain layer.

## Consequences

- Provenance remains straightforward and the repository can retain Apache-2.0 licensing.
- Behavior must be specified independently rather than inherited from another implementation.
- Initial delivery can iterate through HACS, while future Core-quality work remains possible.
- Reviews must reject copied GPL implementation details even when functionally convenient.
