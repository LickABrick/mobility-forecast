# ADR 0006: Require explicit privacy-bounded provider selection

- Status: Accepted
- Date: 2026-09-02
- Supersedes: ADR 0005's first-provider recommendation only

## Context

Routing and geocoding disclose sensitive trip endpoints or calendar location text to different services. Self-hosted OpenRouteService supplies routing but does not bundle a geocoder, so treating it as one complete location service would hide a data recipient. A silent provider default or fallback could send data somewhere the user did not select.

## Decision

Keep geocoding and routing behind provider-neutral typed boundaries and require explicit provider selection and consent. No hosted or self-hosted provider is selected by default, and runtime must never automatically fall back between providers or between hosted and self-hosted modes.

OpenRouteService is the recommended provider family:

- The simple hosted path uses the free hosted ORS routing API and its hosted Pelias geocoder with one explicit user-supplied API key.
- The advanced path configures a self-hosted ORS routing base URL and a separate self-hosted geocoder base URL. Initially supported geocoder families are Pelias, Photon and Nominatim.
- Configuration and help text must name every provider and show every routing and geocoding endpoint that receives coordinates or calendar location text before consent.

Geoapify and Google Routes paired with Google Geocoding remain optional adapter families rather than defaults. Every family must satisfy the same provider-neutral contracts and fail-closed quality semantics.

No network transport may be enabled until hard request budgets, bounded retry behavior and privacy-safe geocode and route cache retention are explicit, configurable where appropriate and covered by synthetic tests. Unattended tests use injected transports and synthetic fixtures only; they never call a public or paid route/geocoder endpoint.

## Consequences

- Schema 1.4's Google-only configuration must be migrated without guessing a replacement provider or silently reusing its credential.
- Hosted users explicitly consent to both routing and geocoding recipients even when one API key authorizes both.
- Self-hosted users configure routing and geocoding independently and are not told that ORS includes geocoding.
- Provider failures stay unavailable or partial; they cannot trigger cross-provider fallback or zero distance.
- Provider adapters may vary, but calendar, itinerary, forecast and entity logic remain provider-independent.
