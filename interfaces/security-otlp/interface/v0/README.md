# `security-otlp`

Lets a workload charm send security-relevant logs directly to a purpose-built collector
(`log-aggregator-k8s`) over OTLP, bypassing the charm's general `otlp`/COS pipeline for this one
class of data.

* `receive-security-otlp` (provider) -- declared by `log-aggregator-k8s`
* `send-security-otlp` (requirer) -- declared by source workload charms (`hydra`, `kratos`)

Logs-only, TLS-required from the first release, no mTLS, no rules. See `schema.py` for the
databag shape.
