# Changelog

## [1.0.0](https://github.com/LickABrick/mobility-forecast/compare/v1.0.0...v1.0.0) (2026-10-20)


### Features

* polish native EV options and correct forecast action horizons ([c99c9e7](https://github.com/LickABrick/mobility-forecast/commit/c99c9e787837313090486004a62d4f9f862df17e))
* ship generated local Home Assistant brand assets ([215acbf](https://github.com/LickABrick/mobility-forecast/commit/215acbf29dab4a742af5407fe36b3fc4f3f8e7b6))


### Bug fixes

* correct Home Assistant documentation links ([4a76b23](https://github.com/LickABrick/mobility-forecast/commit/4a76b2380d2dfecdc588fe0fd0297498754099ff))
* harden Release Please preparation and publication ([5e0a0a5](https://github.com/LickABrick/mobility-forecast/commit/5e0a0a58fba924956a2ee581a4a254891c40ce59))
* harden release readiness, documentation links and CI ([a830df3](https://github.com/LickABrick/mobility-forecast/commit/a830df3da5da3e0d6d122229c5c51cdb2a39d6a0))


### Documentation

* finalize release maintainer instructions ([69d9709](https://github.com/LickABrick/mobility-forecast/commit/69d97092e6adbb6fdb60b27e05a7026337b8952b))
* polish native dashboard and remaining configuration guidance ([28bb52c](https://github.com/LickABrick/mobility-forecast/commit/28bb52c428d5acbd06238127d1af33334b59a524))
* record release readiness evidence and remaining staging gates ([7a673de](https://github.com/LickABrick/mobility-forecast/commit/7a673deeb1155ee33a3f2a7ac433765cd065c1f1))
* reorganize product landing page and task-oriented guides ([f5e115d](https://github.com/LickABrick/mobility-forecast/commit/f5e115dfee51dc17f1581af1bed7a79ddc09d80d))


### Maintenance

* add contribution security and issue reporting standards ([7ce7eb9](https://github.com/LickABrick/mobility-forecast/commit/7ce7eb99494e9846c8c850fce13e5dc3dd6f72df))
* align repository tooling with the default branch ([484218d](https://github.com/LickABrick/mobility-forecast/commit/484218d0096a22daaff68071ade8752f18a1a033))
* avoid duplicate quality runs during release preparation ([e3653c7](https://github.com/LickABrick/mobility-forecast/commit/e3653c7ccce7f4e5b7a71f7cf5dd4d8e76184ceb))
* enforce coverage documentation packaging and release safety checks ([652586a](https://github.com/LickABrick/mobility-forecast/commit/652586a5f68fe44247b4fa9652de5b442fe5ecc2))
* prepare approval-controlled releases with atomic version validation ([4970a01](https://github.com/LickABrick/mobility-forecast/commit/4970a018080588a1e03b1826c8a94b73ed4c7c43))
* prevent duplicate quality runs on pull request branches ([9d1cac9](https://github.com/LickABrick/mobility-forecast/commit/9d1cac9633a47d06bd778d7f802a693e5a309b1b))

## Changelog

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
