# Mobility Forecast

Mobility Forecast is a planned Home Assistant custom integration that turns calendar events into privacy-conscious, provider-independent mobility forecasts. It is designed to compare planned road distance with passively observed odometer changes and publish uncertainty-aware, read-only advice.

## Status

The phase-1 architecture and safe development foundation are complete. Bounded
post-phase work now provides selected-calendar refreshes, explicit profile zone
anchors, conservative local online-event classification, applied structural policy,
real OpenRouteService location/routing composition, isolated Home Assistant contracts
and a reproducible test ZIP. Valid configured physical events can publish real routed
kilometres; failed or incomplete inputs remain unknown rather than becoming zero.
The project must not wake vehicles or execute charging actions.

Profile-scoped provider caches and the bounded production HTTP sender are connected to
the refresh runtime for hosted and self-hosted OpenRouteService profiles. Raw event
locations are sent only to the explicitly selected geocoder, and coordinates only to
the selected router. Geoapify and Google remain selectable future families without a
production adapter and therefore fail closed today.

Schema 1.6 also requires every profile to choose its history threshold, accepted
actual-to-planned correction range and cold-start P90 conservatism explicitly. The
forecast model has no hidden behavioral defaults.

The installed integration is not a synthetic-data demo: configured OpenRouteService
profiles use real calendar and Home Assistant inputs and call the provider explicitly
selected by the user. Synthetic provider data remains confined to automated tests.

See:

- [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/adr/`](docs/adr/)
- [`docs/NIGHTLY_PLAN.md`](docs/NIGHTLY_PLAN.md)
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- [`TESTING.md`](TESTING.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`AGENTS.md`](AGENTS.md)

## Intended V1 boundaries

V1 is read-only and advisory. It may read calendar, location, odometer, SOC and range entities, and call an explicitly configured route provider. It must not start charging, change charge limits, wake a vehicle, control climate, or optimize against energy prices or solar generation.

## License

Apache-2.0.
