# Mobility Forecast

Mobility Forecast is a planned Home Assistant custom integration that turns calendar events into privacy-conscious, provider-independent mobility forecasts. It is designed to compare planned road distance with passively observed odometer changes and publish uncertainty-aware, read-only advice.

## Status

The phase-1 architecture and safe development foundation are complete. Bounded
post-phase work now provides selected-calendar refreshes, explicit profile zone
anchors and structural event policy, isolated Home Assistant contracts and a
reproducible test ZIP. Endpoint and route-provider runtime composition remains
incomplete, so kilometres stay unknown. The project must not wake vehicles or
execute charging actions.

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
