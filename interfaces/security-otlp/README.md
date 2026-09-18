# charmlibs.interfaces.security_otlp

The `security-otlp` library.

Lets a workload charm send a security-relevant, logs-only subset of its telemetry directly to a
purpose-built collector (e.g. `log-aggregator-k8s`), bypassing its general `otlp`/COS pipeline
for this one class of data. See the [security-otlp spec](../../../spec-security-otlp.md) for full
rationale.

## Features

- **Provider/Requirer pattern**: mirrors `otlp`'s split, as a separate, independent package.
- **Logs-only**: every endpoint is implicitly logs-only; there's no `telemetries` filter to configure.
- **TLS-required**: `add_endpoint()` rejects a non-`https://` endpoint immediately, rather than
  allowing it through and relying on documentation.
- **No rules, no requirer-side publish**: this interface carries no LogQL/PromQL rules, so the
  requirer only ever reads.

## Getting started

To install, add `charmlibs-interfaces-security-otlp` to your Python dependencies. Then in your
Python code, import as:

```py
from charmlibs.interfaces.security_otlp import SecurityOtlpProvider, SecurityOtlpRequirer
```

### Provider Side (e.g. `log-aggregator-k8s`)

```python
from charmlibs.interfaces.security_otlp import SecurityOtlpProvider

class MyCollector(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.ingress_ready, self._publish_endpoint)

    def _publish_endpoint(self, event):
        SecurityOtlpProvider(self).add_endpoint(
            protocol="http",
            endpoint="https://log-aggregator.secops.example:4318",
        ).publish()
```

### Requirer Side (e.g. `hydra`, `kratos`)

```python
from charmlibs.interfaces.security_otlp import SecurityOtlpRequirer

class MySourceCharm(CharmBase):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.framework.observe(self.on.update_status, self._access_endpoint)

    def _access_endpoint(self, _: ops.EventBase):
        SecurityOtlpRequirer(self, protocols=["http", "grpc"]).endpoints
```

## Documentation

For complete documentation, see the [charmlibs documentation](https://canonical.com/juju/docs/charmlibs/reference/charmlibs/interfaces/security_otlp).

## Contributing

See [CONTRIBUTING.md](https://github.com/canonical/charmlibs/blob/main/CONTRIBUTING.md) in the repository root.
