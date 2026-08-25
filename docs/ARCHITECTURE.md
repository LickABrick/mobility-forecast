# Architecture

## Design goals

Mobility Forecast separates pure, typed planning and forecasting logic from Home Assistant and external providers. Home Assistant adapters translate entity/config-entry data into domain values; domain services return explicit quality states; presentation adapters expose only read-only results.

The architecture optimizes for profile isolation, deterministic tests, privacy-safe diagnostics and conservative behavior when inputs are missing or stale.

## Context and boundaries

```text
Home Assistant config entry (one forecast profile)
        |
        v
Adapters: calendar | location | vehicle | storage | route provider
        |
        v
Pure domain pipeline
  filter -> resolve endpoints -> route -> assemble plan
         -> match passive actuals -> forecast + quality
        |
        v
Read-only entities | privacy-safe preview | redacted diagnostics
```

External systems are behind typed protocols. Domain objects must not import Home Assistant. Provider-specific request/response types stop at their adapter.

## Forecast profile ownership

Each config entry is an independent composition root. It owns:

- selected calendar sources and filter policy;
- independent start-location and end-location policies;
- route-provider selection and provider-specific configuration;
- explicitly selected passive vehicle sources;
- storage namespace, plan revisions and forecast-model state; and
- coordinator lifecycle and read-only entities.

No mutable cache, history or coordinator state may leak between entries. Reusable code and immutable configuration types may be shared. Provider credentials are referenced through Home Assistant configuration and must not appear in domain values, storage exports or diagnostics.

## Planned domain boundaries

These are responsibilities, not speculative class names. C2 will introduce only contracts with concrete tested uses.

- **Calendar source:** supplies normalized candidate events from configured calendars.
- **Event filter:** deterministically classifies candidates and provides privacy-safe reason counts.
- **Location resolver:** resolves a start or end policy to a location result with provenance, freshness and quality.
- **Route provider:** calculates a directional route between resolved endpoints and returns an explicit success/failure state.
- **Itinerary planner:** orders stops, deduplicates events and preserves partial daily plans.
- **Vehicle source:** supplies passive location, odometer, SOC and range observations without refresh or control methods.
- **Plan repository:** appends immutable plan revisions and observations in a profile-scoped namespace.
- **Forecast model:** estimates distance/readiness with sample quality and uncertainty.

## Endpoint resolution policy

Start and end are separate decisions. The configured origin is not implicitly copied to every destination, and an event location is not implicitly treated as the next trip's origin without itinerary evidence.

A start policy may use a passively observed vehicle location for an applicable near-term trip only when the sample satisfies explicitly configured freshness and quality requirements. It must never request a refresh. If the sample is stale, inaccurate, missing or unsuitable for the trip horizon, resolution uses the configured fallback when available and records that provenance; otherwise it is unavailable.

An end policy resolves the event destination independently from supported event/location data and configured fallbacks. It does not silently substitute the current vehicle position for an unknown destination.

The exact freshness thresholds, horizon rules, accuracy representation and fallback precedence belong to C4 and must be introduced as tested, visible configuration rather than undocumented defaults.

## Route-provider architecture

The domain depends on a provider-neutral, asynchronous route protocol. Requests contain normalized endpoints and route-relevant options; results retain direction, distance, duration, provider provenance, observation time and quality. Failures use typed categories such as unavailable, invalid input, quota/rate limit and transient provider failure.

A route from A to B is not interchangeable with B to A. Cache keys must be profile/privacy safe and include all route-affecting inputs. Cache expiry and stale-result behavior will be specified and tested in C5.

Google Routes is the intended first production adapter, not a domain dependency. Deterministic fakes are the only route providers used during unattended development. Adding another adapter must not change calendar, itinerary or forecast logic.

## State and revision flow

A plan run creates a revision rather than mutating an earlier plan. Each revision records normalized identifiers, source observation times, planned legs and quality/provenance needed to interpret the result. Raw event text, addresses and coordinates must not be copied into diagnostics.

Later calendar edits create a new revision. Passive odometer observations are matched to the revision that was current for the relevant period so model training does not rewrite history. Storage schema and migration mechanics are deferred until their checkpoint; schema changes require explicit versioning and migration tests.

## Quality and failure semantics

Quality is part of the domain result, not an incidental log message:

- **complete:** all required legs use acceptable current inputs;
- **partial:** useful planning exists but one or more legs/inputs are unresolved;
- **stale:** a retained result is usable only with explicit age/provenance;
- **unavailable:** no defensible result can be produced.

A failure may reduce confidence or suppress advice. It must not create a zero-distance leg, erase a prior plan, or imply vehicle readiness. Forecast outputs carry uncertainty and enough reason metadata for a redacted user-facing explanation.

## Home Assistant boundary

The eventual integration layer will provide config flow, options/migrations, coordinator lifecycle, read-only entities, translations and redacted diagnostics. It may call only read methods on configured sources. No service registration for vehicle, charging, climate or notification actions belongs in V1.

Home Assistant configuration/schema files do not yet exist. Their defaults and versions will be introduced at C8, after the underlying domain contracts are tested; no configuration default is established by this architecture checkpoint.

## Test strategy

- Pure domain behavior: unit tests with typed synthetic values.
- Boundaries: contract tests against deterministic fakes.
- Storage: round-trip, revision-preservation and migration tests.
- Home Assistant adapters: isolated fixtures with synthetic entity states.
- Privacy: tests asserting diagnostics/log output excludes event text, addresses and coordinates.
- Route providers: recorded or synthetic fixtures only unless a later explicitly authorized manual test supplies dedicated credentials.

No test may access production Home Assistant, personal data, vehicle services or real route endpoints.
