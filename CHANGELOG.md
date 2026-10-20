# Changelog

## Unreleased

Initial public release preparation; no release has been published by this work.
The existing 1.0.0 metadata is a bootstrap target, not evidence of a published tag.

### Features

- Local mileage forecasting, calendar routes, history comparisons and manual sync.
- Optional experimental EV charging estimates; no automatic vehicle control.
- Native EV submenu, number/time selectors, contextual English/Dutch help and
  conservative same-device numeric suggestions.
- Local Home Assistant branding and task-oriented user/developer guides.

### Bug fixes

- `get_forecast(days)` now honors the requested local date count. Default action
  responses return 30 rather than the former fixed 31; request 31 explicitly if needed.
  Mileage Timeline retains its display contract.

### Limitations

- EV remains experimental; NDW unit/access ambiguity is rejected conservatively.
- Real HAOS staging and first-release workflow execution remain maintainer gates.
