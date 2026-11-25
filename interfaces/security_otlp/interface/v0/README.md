# `security_otlp`

Lets a workload charm send security-relevant logs to a collector over OTLP, separately from the
charm's general logging and `otlp` integrations.

* `receive-security-otlp` (provider) -- declared by `log-aggregator-k8s`
* `send-security-otlp` (requirer) -- declared by source workload charms (`hydra`, `kratos`)

Logs-only, TLS-required from the first release, no mTLS, no rules. See `schema.py` for the
databag shape.
