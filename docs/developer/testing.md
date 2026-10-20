# Testing

Use the [contributor commands](../../CONTRIBUTING.md#environment) with Python 3.14.2+
and pinned HA 2026.10.2. Tests use the HA fixture framework with mocked Recorder and
external providers. Mandatory CI never needs private locations or live provider calls.

Coverage is measured with pytest-cov; terminal missing-line output and XML are retained.
The initial complete-suite baseline measured 86.53% statement coverage; CI uses an
85% floor to detect meaningful regressions without pretending coverage proves correctness. Mypy checks fourteen selected domain modules, not strict full coverage.
Hassfest and HACS remain separate required jobs. YAML parsing checks syntax but does
not prove GitHub workflow semantics or third-party Lovelace behavior.

For new changes prioritize actions/flow preservation, storage compatibility, worker
cancellation, two-entry isolation, reserve/timing semantics and privacy over superficial
coverage gains. Run focused tests before committing and the whole suite before release.
Use [staging](staging-validation.md) for the remaining real-runtime evidence.
