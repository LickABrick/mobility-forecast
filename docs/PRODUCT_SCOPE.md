# Product scope

## Purpose

Mobility Forecast is a Home Assistant custom integration that converts selected calendar events into an uncertainty-aware forecast of road travel and vehicle readiness. It compares planned distance with passively observed vehicle data so the advice can improve without controlling the vehicle.

The integration is HACS-first and clean-room. It may cite Smart EV Trip Planner as prior art, but its design and implementation must not copy GPL source.

## V1 user outcome

For each independently configured forecast profile, V1 should:

1. read events from explicitly selected calendar entities;
2. apply deterministic, inspectable event filters;
3. resolve each trip endpoint under separate start and end policies;
4. request directional road routes through a provider-neutral boundary;
5. combine chronological trips into a daily plan with explicit data quality;
6. compare immutable plan revisions with passive odometer observations;
7. publish estimated distance and SOC/readiness advice with uncertainty, including P50 and conservative P90 values; and
8. expose privacy-safe setup previews and diagnostics.

Advice must distinguish complete, partial, stale and unavailable inputs. Missing route or vehicle data must never be converted into zero distance or a false “charging not needed” conclusion.

## Inputs and outputs

V1 may read only entities and providers that the user explicitly configures:

- calendar event timing and location fields needed for planning;
- Home Assistant zones or another configured location source;
- passive vehicle location, odometer, SOC and estimated-range states;
- route results from the selected route provider; and
- integration-owned historical plans and observations.

V1 outputs read-only forecast entities, setup/preview summaries and redacted diagnostics. Event text, addresses and coordinates are operational inputs, not diagnostic or log output.

## Non-goals

V1 does not:

- start or stop charging, change charge limits or optimize a charging schedule;
- control climate, locks, plugs, lights or any other physical service;
- wake a vehicle or request an active refresh;
- send notifications;
- optimize against electricity prices, tariffs, grid signals or solar production;
- modify calendar events;
- infer or select a vehicle automatically;
- require one particular calendar, vehicle or route-provider integration;
- promise exact distance, consumption or arrival SOC; or
- provide live navigation, traffic guidance or safety-critical advice.

Charging optimization may later consume Mobility Forecast output as a separate integration or subsystem. It is not part of the V1 execution boundary.

## Configuration boundary

One Home Assistant config entry represents one forecast profile. A profile owns its selected calendars, event filtering, endpoint policies, route-provider configuration, vehicle sources and forecast history. Multiple entries must coexist without sharing mutable profile state.

Schema fields, thresholds and defaults are intentionally deferred until their behavior can be specified and tested in the relevant checkpoint. This document does not introduce hidden defaults.

## Safety and privacy invariants

- All behavior is advisory and read-only.
- Vehicle information is sampled passively; no code path may wake or command a vehicle.
- Route failures remain explicit and degrade forecast quality.
- Start and end locations are resolved independently.
- Historical plan revisions remain immutable so later calendar edits do not rewrite training truth.
- Logs and diagnostics redact event text, addresses and coordinates.
- Tests use synthetic fixtures and deterministic fakes; unattended development never calls a real route API or production Home Assistant.

## Acceptance boundary for V1

V1 is complete only when a user can configure more than one isolated profile, preview what will be considered without exposing event details, obtain read-only forecasts with visible quality/uncertainty, and inspect redacted diagnostics. Every degraded state must remain conservative and explainable.

The production integration must operate on the user's configured Home Assistant
entities and make real geocoding and routing requests to the explicitly selected
provider. Deterministic synthetic data is a test strategy, not a production mode or
substitute for this acceptance boundary. Provider calls require the user's affirmative
location-data consent, configured credential or self-hosted endpoints, bounded request
policy and private cache; disabling or failing a provider must degrade explicitly.
