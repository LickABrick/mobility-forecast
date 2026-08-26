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

Later calendar edits create a new revision. The pure append contract rejects duplicate revision identifiers and non-increasing creation times, returns a new immutable history tuple and leaves earlier objects unchanged. Passive odometer observations are matched to the revision that was current for the relevant period so model training does not rewrite history.

C8c defines initial storage schema version 1 for immutable plan revisions, pending days and closed actuals. Each payload is addressed only by `mobility_forecast.<config entry id>`; profile titles are not storage namespaces. Encoding is JSON-safe, decoding reconstructs validated frozen domain values, and unknown schema versions fail closed until an explicit migration is implemented. Payloads necessarily retain operational identifiers and coordinates required to reconstruct historical plans, so raw storage must remain profile-local and must never be copied into diagnostics or logs.

C7 captures that match when a pending day opens: it selects the latest complete revision for the service date whose creation time is not later than the opening time, snapshots its complete positive routed distance and revision identifier, and never consults later edits when closing. Start and end odometer samples are passive inputs accepted only when present, not future-dated and within an explicit inclusive maximum age. Closure additionally requires a newer end sample, a nondecreasing odometer and an explicit maximum daily-distance gate. Rejected samples and incomplete plans cannot become training actuals.

The baseline forecast trains only on complete closed actuals with a positive captured plan. Historical actual/planned ratios outside explicit inclusive correction bounds are classified as outliers. If fewer than the explicit minimum number of inliers remain, cold start uses the current uncorrected complete plan as P50 and an explicit multiplier of at least one for P90, with `partial` quality. Otherwise P50 uses the median inlier correction and P90 uses the greater of that median and nearest-rank 90th percentile. A current incomplete or unavailable plan produces no distance percentiles rather than a zero. All age, distance, sample-count, correction-bound and cold-start values are required domain inputs; C7 introduces no product default.

## Quality and failure semantics

Quality is part of the domain result, not an incidental log message:

- **complete:** all required legs use acceptable current inputs;
- **partial:** useful planning exists but one or more legs/inputs are unresolved;
- **stale:** a retained result is usable only with explicit age/provenance;
- **unavailable:** no defensible result can be produced.

A failure may reduce confidence or suppress advice. It must not create a zero-distance leg, erase a prior plan, or imply vehicle readiness. Forecast outputs carry uncertainty and enough reason metadata for a redacted user-facing explanation.

## Home Assistant boundary

The integration layer will provide config flow, options/migrations, coordinator lifecycle, read-only entities, translations and redacted diagnostics. The first C8 slice establishes a versioned, JSON-safe diagnostics projection that accepts only typed aggregate counts, stable reason categories, quality and generation time. Profile names, entity/event identifiers, event text, addresses, coordinates, provider details and credentials cannot enter that projection. The later Home Assistant diagnostics adapter must construct this snapshot rather than serializing config-entry or coordinator objects directly.

The integration layer may call only read methods on configured sources. No service registration for vehicle, charging, climate or notification actions belongs in V1. C8b adds minimal custom-integration/HACS metadata and config-entry schema version 1 (minor version 1). Its user flow requires only a profile name, uses that name solely as the entry title and stores an empty data mapping, so it establishes no calendar, location, vehicle, route or threshold default. It deliberately assigns no unique ID so multiple independently titled profile entries remain possible. The C8c codec is still a dependency-free boundary contract: a later adapter must connect it to Home Assistant storage without logging or diagnosing raw payloads.

C8d adds the dependency-free coordinator contract used by that future adapter. Each coordinator is constructed with exactly one config-entry identifier, a typed source exposing only `read(previous_state)`, and typed storage whose load/save calls always require that identifier. A refresh loads immutable prior state, reads one validated update, persists its next state, and only then publishes an immutable, chronologically ordered forecast snapshot. Read or save failures propagate without replacing the last published snapshot, so entities cannot observe state that was never durably accepted. Source adapters remain responsible for composing the already-tested pure pipeline; the coordinator adds no active refresh, service, credential, notification or external-provider capability.

C8e adds one thin sensor-platform adapter over that immutable snapshot. Each config entry receives exactly one read-only forecast-distance sensor whose state is the earliest service day's conservative P90 distance in kilometres. P50 distance, service date, quality and generation time are a fixed attribute allowlist; arbitrary reason text and all source/entity/event/location/provider identifiers are excluded. A missing distance remains an unknown value rather than becoming zero, while a persisted degraded snapshot remains inspectable through its quality attribute. The entity implements no polling, refresh or action method. Config-entry lifecycle composition and forwarding of the sensor platform remain deferred until the source and storage adapters can construct a real coordinator without invented defaults.

## Test strategy

- Pure domain behavior: unit tests with typed synthetic values.
- Boundaries: contract tests against deterministic fakes.
- Storage: round-trip, revision-preservation and migration tests.
- Home Assistant adapters: isolated fixtures with synthetic entity states.
- Privacy: tests asserting diagnostics/log output excludes event text, addresses and coordinates.
- Route providers: recorded or synthetic fixtures only unless a later explicitly authorized manual test supplies dedicated credentials.

No test may access production Home Assistant, personal data, vehicle services or real route endpoints.
