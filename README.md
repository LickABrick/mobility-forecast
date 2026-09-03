# Mobility Forecast

Mobility Forecast is a planned Home Assistant custom integration that turns calendar events into privacy-conscious, provider-independent mobility forecasts. It is designed to compare planned road distance with passively observed odometer changes and publish uncertainty-aware, read-only advice.

## Status

The phase-1 architecture and safe development foundation are complete. Bounded
post-phase work now provides selected-calendar refreshes, explicit profile zone
anchors, conservative local online-event classification, applied structural policy,
isolated Home Assistant contracts and a reproducible test ZIP. Event-location and
route-provider runtime composition remain incomplete, so kilometres stay unknown.
The project must not wake vehicles or execute charging actions.

Profile-scoped provider cache persistence and a bounded production HTTP sender over
Home Assistant's managed client are implemented, including opaque keys, retention
pruning, atomic privacy-key rotation, disabled redirects and sanitized failures. They
are not yet connected to the production refresh runtime.

The intended integration is not a synthetic-data demo. Once the remaining network and
runtime checkpoints are complete, configured profiles will use their real calendar and
Home Assistant inputs and call the provider explicitly selected by the user. Synthetic
provider data remains confined to automated tests.

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
