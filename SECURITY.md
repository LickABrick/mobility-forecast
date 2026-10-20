# Security policy

Security fixes target the latest published release. Until a first public release,
only the current default branch receives fixes; older snapshots are unsupported.
EV remains experimental, independently of mileage release maturity.

Report vulnerabilities privately using GitHub **Security → Advisories → Report a
vulnerability** for this repository. The owner must enable private vulnerability
reporting; see [maintainer setup](docs/developer/repository-setup.md). If the button
is unavailable, ask the owner in a public issue to enable private reporting, without
posting exploit details or private data. No reporting email is currently designated.

Describe affected versions, impact and minimal sanitized reproduction. Allow time
for investigation and coordinated disclosure; avoid publishing working exploits
before a fix is available. No response-time SLA or bounty is promised.

Relevant boundaries include Home Assistant state/permissions, mileage persistence,
calendar/location data, vehicle telemetry and optional external Waze/PDOK/NDW queries.
Never attach credentials, raw calendar events, home addresses, vehicle identifiers
or full private storage. Diagnostics and debug logs should be reviewed before sharing.
