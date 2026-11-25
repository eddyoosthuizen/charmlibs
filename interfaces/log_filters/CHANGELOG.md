# Changelog

All notable changes to the charmlibs.interfaces.log_filters library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial version of charmlibs.interfaces.log_filters
- `LogFiltersRequirer` for publishing a charm's OTTL drop conditions and Juju topology
- `LogFiltersProvider.resolve_sources()` for reading them, checking each relation's claimed
  topology against what Juju reports, and refusing a second claim on one source
- Rule sets keyed by language (`filters.ottl`); unknown languages are ignored
- `forward_logs_over_otlp` for forwarding a container's Pebble service logs to the endpoints of an
  `otlp` relation through Pebble `opentelemetry` log targets, without publishing to that relation
- `plan_contains_layer` for skipping an `add_layer` that would not change the plan
