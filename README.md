# Mobility Forecast

Mobility Forecast is a planned Home Assistant custom integration that turns calendar events into privacy-conscious, provider-independent mobility forecasts. It is designed to compare planned road distance with passively observed odometer changes and publish uncertainty-aware, read-only advice.

## Status

This repository is in phase 1: architecture, contracts, tests and a safe development foundation. Nothing in this repository is installed in production Home Assistant, and the project must not wake vehicles or execute charging actions.

See:

- [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/adr/`](docs/adr/)
- [`docs/NIGHTLY_PLAN.md`](docs/NIGHTLY_PLAN.md)
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`AGENTS.md`](AGENTS.md)

## Intended V1 boundaries

V1 is read-only and advisory. It may read calendar, location, odometer, SOC and range entities, and call an explicitly configured route provider. It must not start charging, change charge limits, wake a vehicle, control climate, or optimize against energy prices or solar generation.

## License

Apache-2.0.
