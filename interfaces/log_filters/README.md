# charmlibs.interfaces.log_filters

The `log_filters` library.

Lets a charm publish the rules for filtering its own logs, so that the collector it sends them to
drops what the charm says is noise before anything is forwarded. The charm owns its rules; the
collector applies them. Also ships `forward_logs_over_otlp`, which forwards a container's Pebble
service logs over an existing `otlp` relation.

## Features

- **Requirer publishes, provider applies**: the requirer publishes OTTL drop conditions and its
  Juju topology; the provider reads them per relation.
- **Topology checks**: each relation's claimed topology is checked against what Juju reports, and a
  source claimed by two relations stays with the older one.
- **Language-keyed rules**: rule sets are keyed by language, so new languages can be added; a
  provider ignores the ones it does not support.
- **Pebble forwarding over `otlp`**: one `opentelemetry` log target per `otlp` relation, labelled
  with the unit's topology, for Pebble 1.24 or later.

## Getting started

To install, add `charmlibs-interfaces-log-filters` to your Python dependencies. Then in your
Python code, import as:

```py
from charmlibs.interfaces.log_filters import LogFiltersRequirer, forward_logs_over_otlp
```

See the package docstring for usage on both sides.

## Contributing

See [CONTRIBUTING.md](https://github.com/canonical/charmlibs/blob/main/CONTRIBUTING.md) in the repository root.
