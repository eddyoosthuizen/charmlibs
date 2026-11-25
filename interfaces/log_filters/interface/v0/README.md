# `log_filters`

Lets a charm publish the rules for filtering its own logs to the collector it sends them to. The
logs themselves travel over any relation, such as `otlp` or `loki_push_api`; the collector matches
rules to logs by the Juju topology the rules carry.

* `send-log-filters` (requirer): declared by charms whose logs are filtered (`hydra`, `kratos`)
* `receive-log-filters` (provider): declared by collectors that apply the filters (`log-aggregator-k8s`)

The requirer's app databag carries `metadata` (its topology) and `filters`, keyed by rule
language; `ottl` is the only language in version 0. The provider writes nothing. See `schema.py`.
