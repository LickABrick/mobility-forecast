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

A start policy may use a passively observed vehicle location for an applicable near-term trip only when the sample satisfies explicitly configured freshness and quality requirements. It must never request a refresh. The policy requires maximum sample age, maximum reported accuracy radius in metres and maximum trip horizon; the domain establishes no numeric defaults. Limits are inclusive. A missing observation time, future-dated observation, unknown accuracy, excessive age or accuracy, or trip beyond the horizon rejects the vehicle candidate. Resolution then uses a configured fallback with `partial` quality when available; otherwise it is `unavailable`. The privacy-safe reason preserves which gate rejected the sample.

An end policy resolves an event- or zone-derived destination independently. Its required fallback flag explicitly permits or forbids a configured destination fallback; a used fallback has `partial` quality. It does not accept or silently substitute the current vehicle position for an unknown destination.

These C4 policy values are required pure-domain inputs. Home Assistant config-flow representation and any user-facing defaults remain deferred to C8 and must not silently alter this contract.

## Route-provider architecture

The domain depends on a provider-neutral, asynchronous route protocol. Requests contain private normalized endpoints, an optional departure time and required toll/highway avoidance choices; no option default is established in the domain. Results retain direction, distance, duration, provider provenance, observation time and quality. Failures expose only stable privacy-safe categories: unavailable, invalid input, quota exhausted, rate limited and transient provider failure.

A route from A to B is not interchangeable with B to A. Cache keys HMAC all route-affecting inputs, including a required stable non-secret provider/config namespace, with required profile-local key material. They retain no raw coordinates or endpoint identifiers and cannot be shared across profile caches. Required inclusive maximum-fresh and maximum-stale ages have no domain defaults. A fresh hit avoids a provider call; a stale hit is refreshed, falls back with explicit `stale` quality and the refresh-failure category only when refresh fails, and is discarded after the stale limit. Provider and cache direction mismatches are rejected. Only complete successful provider routes are cached; failures never become zero distance.

Google Routes is the intended first production adapter, not a domain dependency. Deterministic fakes are the only route providers used during unattended development. Adding another adapter must not change calendar, itinerary or forecast logic.

## State and revision flow

A plan run creates a revision rather than mutating an earlier plan. Each revision records normalized identifiers, source observation times, planned legs and quality/provenance needed to interpret the result. Raw event text, addresses and coordinates must not be copied into diagnostics.

C6 requires each filtered calendar candidate to carry an explicit adapter-normalized deduplication key rather than guessing identity from private event text or locations. Candidates sharing a key deduplicate only when their time range, resolved destination and destination reason agree; conflicts fail explicitly. The deterministic representative and source references use source/event identifier ordering, while stops are ordered by start time, end time and references.

The first leg starts at the independently resolved initial origin. Each later leg starts at the preceding stop's destination, even when routing that preceding leg failed, because a route failure does not erase a known endpoint. An unknown destination breaks subsequent chaining until a future planning policy supplies another defensible origin. Missing endpoints are `unavailable` legs; typed route failures are `partial` legs; stale and partial endpoint/route quality propagate without becoming a zero-distance success. A non-empty day with any degraded leg is partial, while a day with no stops is unavailable.

Later calendar edits create a new revision. The pure append contract rejects duplicate revision identifiers and non-increasing creation times, returns a new immutable history tuple and leaves earlier objects unchanged. Passive odometer observations are matched to the revision that was current for the relevant period so model training does not rewrite history. Persistent repository/storage schema and migration mechanics are deferred until their checkpoint; schema changes require explicit versioning and migration tests.

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
