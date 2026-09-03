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

These boundaries are seams for safety and testing, not a replacement for production
I/O. The completed integration must connect them to Home Assistant's HTTP client and
the user's explicitly configured real provider. Synthetic calendars, locations and
provider responses are permitted only in tests; they must never be selected as a
production forecast source.

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

P15 adds a provider-neutral asynchronous event-location resolver contract. Its minimal request contains only required physical location text—not event summary, description, source or identifier—and hides that private text from representations. Successful coordinates are also representation-hidden and become an event-provenance candidate only with a caller-owned opaque endpoint identifier. Failures expose only an aware occurrence time and one stable category: invalid input, not found, rate limited, quota exhausted, transient or unavailable. The exact deterministic resolver fake stores only synthetic in-memory fixtures and has no provider, credential, cache, filesystem or network path. Production provider selection, credential handling and cache retention remain explicit review decisions; no live event-location resolution is composed.

These C4 policy values are required pure-domain inputs. Home Assistant config-flow representation and any user-facing defaults remain deferred to C8 and must not silently alter this contract.

## Route-provider architecture

The domain depends on a provider-neutral, asynchronous route protocol. Requests contain private normalized endpoints, an optional departure time and required toll/highway avoidance choices; no option default is established in the domain. Results retain direction, distance, duration, provider provenance, observation time and quality. Failures expose only stable privacy-safe categories: unavailable, invalid input, quota exhausted, rate limited and transient provider failure.

A route from A to B is not interchangeable with B to A. Cache keys HMAC all route-affecting inputs, including a required stable non-secret provider/config namespace, with required profile-local key material. They retain no raw coordinates or endpoint identifiers and cannot be shared across profile caches. Required inclusive maximum-fresh and maximum-stale ages have no domain defaults. A fresh hit avoids a provider call; a stale hit is refreshed, falls back with explicit `stale` quality and the refresh-failure category only when refresh fails, and is discarded after the stale limit. Provider and cache direction mismatches are rejected. Only complete successful provider routes are cached; failures never become zero distance.

OpenRouteService is the recommended production provider family, not a domain
dependency. Hosted mode pairs the free ORS routing API with its hosted Pelias
geocoder using one explicit user-supplied API key and consent to send calendar
locations to both named endpoints. Advanced mode configures a self-hosted ORS routing
base URL and a separate self-hosted Pelias, Photon or Nominatim geocoder base URL;
self-hosted ORS does not bundle geocoding. Geoapify and Google Routes+Geocoding remain
optional adapters. Selection is explicit, provider fallback is forbidden, and every
location recipient must be disclosed. Deterministic fakes are the only providers used
during unattended development; hard budgets, bounded retries and privacy-safe
geocode/route caches are prerequisites for network transport.

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

The integration layer will provide config flow, options/migrations, coordinator lifecycle, read-only entities, translations and redacted diagnostics. The first C8 slice establishes a versioned, JSON-safe diagnostics projection that accepts only typed aggregate counts, stable reason categories, quality and generation time. Profile names, entity/event identifiers, event text, addresses, coordinates, provider details and credentials cannot enter that projection. The Home Assistant diagnostics adapter consumes that snapshot through an entry-scoped typed runtime source; it never traverses or serializes config-entry metadata, configuration, options, coordinator objects or private storage.

The integration layer may call only read methods on configured sources. No service registration for vehicle, charging, climate or notification actions belongs in V1. C8b adds minimal custom-integration/HACS metadata and config-entry schema version 1 (minor version 1). Its user flow requires only a profile name, uses that name solely as the entry title and stores an empty data mapping, so it establishes no calendar, location, vehicle, route or threshold default. It deliberately assigns no unique ID so multiple independently titled profile entries remain possible. The C8c codec remains a dependency-free boundary contract; P2 connects it to a private, atomic Home Assistant Store without logging or diagnosing raw payloads.

C8d adds the dependency-free coordinator contract used by the P2 Store adapter and future source adapters. Each coordinator is constructed with exactly one config-entry identifier, a typed source exposing only `read(previous_state)`, and typed storage whose load/save calls always require that identifier. A refresh loads immutable prior state, reads one validated update, persists its next state, and only then publishes an immutable, chronologically ordered forecast snapshot. Read or save failures propagate without replacing the last published snapshot, so entities cannot observe state that was never durably accepted. Source adapters remain responsible for composing the already-tested pure pipeline; the coordinator adds no active refresh, service, credential, notification or external-provider capability.

C8e adds one thin sensor-platform adapter over that immutable snapshot. Each config entry receives exactly one read-only forecast-distance sensor whose state is the earliest service day's conservative P90 distance in kilometres. P50 distance, service date, quality and generation time are a fixed attribute allowlist; arbitrary reason text and all source/entity/event/location/provider identifiers are excluded. A missing distance remains an unknown value rather than becoming zero, while a persisted degraded snapshot remains inspectable through its quality attribute. The entity implements no polling, refresh or action method.

C8f adds the Home Assistant `async_get_config_entry_diagnostics` adapter and an immutable profile runtime composition root. The runtime holds the existing profile coordinator for entities and a typed asynchronous diagnostics source for the adapter, avoiding incompatible uses of `ConfigEntry.runtime_data`. Diagnostics source failures propagate rather than triggering a fallback dump. Construction of the concrete aggregate source remains part of later lifecycle composition; the adapter itself has no network, storage traversal, service, refresh or notification capability.

P1 adds the real config-entry setup/unload hooks and forwards only the sensor platform. Setup creates a distinct runtime per entry before forwarding. Successful platform unload clears runtime data, while failed unload retains it for entities that remain loaded. The lifecycle creates no task, timer, update interval or provider call.

P2 replaces only the pending storage boundary. Each runtime constructs one Home Assistant Store from the config-entry identifier and storage schema version, with privacy and atomic-write behavior selected explicitly. An absent store decodes as immutable empty profile state; present malformed or unsupported payloads fail closed. The adapter rejects cross-entry load/save calls, survives runtime restart through the durable Store key, and is never removed during unload. The source and diagnostics boundaries remain pending, so coordinator refresh still fails before publishing a forecast and no scheduling default is introduced.

P3 introduces config-entry schema version 1 minor version 2. Every newly created
profile must explicitly select a non-empty, ordered, duplicate-free list of
`calendar` entity identifiers; this is required profile ownership, not a hidden
calendar default. Version 1.1 entries had empty data and migrate to an explicit
empty legacy-unconfigured marker so no source is guessed. That marker fails the
strict source decoder until a later reconfiguration flow is implemented. The
read-only calendar adapter resolves only the configured entities, queries one
explicit timezone-aware window, and maps Home Assistant `CalendarEvent` fields
into frozen `SourceEvent` values. Provider-specific online classification remains
an injected policy because Home Assistant 2026.8.1 exposes no provider-neutral
online-event field. Missing entities, identifiers, invalid events and provider
read errors fail with stable private-data-free reason codes. The adapter does not
yet compose the filter, location, routing, planning or forecast pipeline and does
not schedule reads.

P4 adds only a reusable synthetic smoke harness under `tests/`. It composes the
calendar adapter, explicit filtering and fixture endpoint mapping, deterministic
route provider, immutable revision, cold-start forecast, transactional coordinator
and passive sensor. A complete fixture route reaches a nonzero sensor value; a
typed route failure remains unknown rather than becoming zero. This validates
contract compatibility but deliberately does not provide the production profile
source, location adapter, refresh schedule or runtime policy.

P11 connects each entry's selected calendars to bounded production refreshes but
continues to publish date-only unavailable-distance forecasts. P12 advances config
entry schema 1.2 to 1.3 and requires new profiles to select independent start and
end Home Assistant zone anchors plus explicit include/exclude choices for physical,
online, all-day and physical no-location events. The choices have no boolean or
anchor defaults. A frozen decoder omits operational zone identifiers from its
representation and maps structural choices to the pure event-filter contract;
online events remain exempt from a physical-location requirement.

Version 1.2 entries retain their validated calendar selection during migration but
receive no guessed anchors or event behavior. Home Assistant's reconfigure flow can
add or replace the six planning fields while preserving calendars and reloading the
entry. P16 consumes those fields in production date ingestion: a conservative local
classifier marks only standalone HTTPS meeting links on reviewed hosts as online,
then the pure structural filter runs before service-date projection. Included dates
still report `forecast_pipeline_unconfigured` and no kilometres because event
locations and routing remain absent. No external provider or physical-action path is
introduced by this composition.

P13 advances config-entry schema 1.3 to 1.4 with an explicit Google Routes provider,
private credential and toll/highway choices. Its adapter stops at an injected typed
transport, so no HTTP implementation or unattended provider call exists. P17 advances
schema 1.4 to 1.5 and corrects that inactive Google-only shape before transport: every
new/reconfigured profile explicitly selects hosted ORS, self-hosted ORS with a separate
Pelias/Photon/Nominatim geocoder, optional Geoapify or optional Google; accepts the
location-data disclosure; and supplies bounded request, retry, timeout and cache
retention values. Hosted recipients are exact fixed endpoints, while self-hosted
routing and geocoder URLs are independent required fields. Legacy 1.4 migration drops
its provider marker and credential without choosing a replacement. HMAC cache keys
retain no raw location text or coordinates. This remains configuration/domain policy;
no HTTP client, provider fallback or production network composition exists.

P18 adds the OpenRouteService execution adapters without crossing that network
boundary. Hosted mode binds only the fixed ORS Pelias and routing endpoints to the
same explicit key; self-hosted mode binds the independently configured geocoder type,
geocoder endpoint and routing endpoint with no implied bundled geocoder. A shared
refresh-scoped counter charges every transport attempt against separate geocode and
route budgets. Only typed rate-limit/transient failures retry, every attempt has the
configured timeout, and budget exhaustion fails closed. Successful geocodes use
profile-keyed HMAC cache keys and are deleted after their configured retention;
routes use the existing directional cache contract, which now also deletes expired
entries while retaining explicit stale fallback. All request objects hide location
text, coordinates, credentials and configured endpoints from representations. The
adapters accept injected typed transports only: there is still no HTTP client,
production runtime composition, provider fallback or unattended external request.

P19 adds concrete request shaping and response decoding behind a still-injected HTTP
sender. Hosted Pelias uses its fixed GET recipient and the same explicit authorization
key as fixed-endpoint ORS routing. Self-hosted Pelias, Photon and Nominatim append only
`/v1/search`, `/api` and `/search` respectively to the separately configured geocoder
base URL; self-hosted ORS appends `/v2/directions/driving-car` to its independent routing
base URL and receives no hosted key. ORS routes use minimal JSON POST bodies, with
longitude/latitude order, disabled geometry/instructions, metre units, explicit avoid
features and local departure time when supplied. Decoders accept only finite Point
coordinates and positive route summaries; empty geocodes, malformed successes, sender
failures and non-success statuses become stable typed failures without provider body,
request or credential details. HTTP values hide URLs, headers, query text, bodies and
responses from representations. No socket-capable sender is implemented or composed,
so there is still no production network path, provider fallback or external request.

P20 adds a separate schema-version-1 private provider-cache Store for each config
entry. On first initialization it generates and durably saves exactly 32 random bytes
of profile-local HMAC key material before exposing the caches. Restart restores that
same key and opaque geocode/route entries; unsupported or malformed payloads fail
closed without generating a replacement or overwriting evidence. Initialization
prunes every expired or future-dated entry using the profile's explicit geocode and
maximum-stale route ages, including entries that are never looked up again. Explicit
key rotation atomically persists a new key and empty caches so entries derived from
old key material cannot remain unreachable indefinitely. Cache mutations publish
in-memory state only after Home Assistant's private atomic Store accepts the complete
next payload. This storage is an adapter supplied to the existing cache protocols; it
is not composed into the runtime and adds no HTTP sender or provider call.

P21 implements the production `InjectedHttpSender` boundary over Home Assistant's
managed shared HTTP session. It transmits the already-shaped private URL, headers,
query and JSON body only to the selected recipient, disables redirects so credentials
and location data cannot cross to an undisclosed host, and uses the caller's existing
per-attempt timeout. A successful response is streamed in bounded chunks with a hard
1 MiB decoded-body limit before strict UTF-8 JSON parsing. Non-success response bodies
are never read or retained. Connection, timeout and stream failures become a stable
transient sender failure; oversized, invalid UTF-8 or invalid JSON responses become
unavailable, without exception or body text. Task cancellation propagates. The sender
is real production I/O code, while its tests inject protocol-compatible sessions and
make no external request. Runtime composition remains P23 work.

P22 advances config-entry schema 1.5 to 1.6 with the forecast model policy that
production composition requires. Every new or reconfigured profile explicitly chooses
the minimum valid history count, inclusive minimum/maximum accepted actual-to-planned
correction percentages, and cold-start P90 percentage. Persisted percentages are
JSON-safe integers and project to the existing ratio-based `ForecastPolicy`; the form
supplies bounds but no defaults. Schema-1.5 entries retain their complete calendar,
planning and provider configuration during migration but gain no guessed forecast
policy, so reconfiguration is required before routed composition. P23 owns that
composition.

P23 composes the supported production path. Config-entry setup initializes the
profile-local privacy key and persistent provider caches, then each refresh constructs
a new budget-scoped hosted or self-hosted OpenRouteService geocoder/router pair over
Home Assistant's managed session. Only structurally included physical event locations
are geocoded. Included no-location events use the independently configured end anchor
as an explicit partial fallback; online events create no physical trip. Daily
itineraries start at the configured start anchor, retain failed legs as degraded data,
append a new immutable revision and use the schema-1.6 policy to publish P50/P90
distance. Provider or input failures remain unavailable rather than zero. Geoapify
and Google selections still have no production adapter and fail closed.

P14 adds a read-only Home Assistant state-machine boundary for the two configured
zone anchors. Each refresh looks up exactly those selected zone entities and reads
only their latitude/longitude attributes. Valid coordinates become independent
complete `ResolvedLocation` values with opaque `anchor:start` and `anchor:end`
identifiers; the selected entity IDs and coordinate values are hidden from adapter,
snapshot and error representations. Missing state, missing coordinates, nonnumeric
values and out-of-range values fail closed with stable role-specific reasons before
calendar ingestion, which makes the latest entity update unavailable while retaining
prior immutable coordinator data. The resolved coordinates are not projected. P16
applies structural filtering after anchor resolution, and P23 supplies event
geocoding, routing and road kilometres for supported OpenRouteService configurations.

## Test strategy

- Pure domain behavior: unit tests with typed synthetic values.
- Boundaries: contract tests against deterministic fakes.
- Storage: round-trip, revision-preservation and migration tests.
- Home Assistant adapters: isolated fixtures with synthetic entity states.
- Privacy: tests asserting diagnostics/log output excludes event text, addresses and coordinates.
- Route providers: recorded or synthetic fixtures only unless a later explicitly authorized manual test supplies dedicated credentials.

No test may access production Home Assistant, personal data, vehicle services or real route endpoints.
Production code, by contrast, must call the selected real provider when the user has
configured consent and credentials/endpoints; automated verification proves that path
with protocol-compatible fakes rather than making an unattended external request.
