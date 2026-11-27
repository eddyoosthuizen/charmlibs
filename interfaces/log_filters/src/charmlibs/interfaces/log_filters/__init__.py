# Copyright 2026 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Log filters Provider and Requirer library.

The ``log_filters`` interface lets a charm publish the rules for filtering its own logs, so that
the collector it sends them to drops what the charm says is noise before anything is forwarded.
The charm owns its rules; the collector applies them. The interface carries rules and the
charm's Juju topology only: the logs themselves travel over any relation, such as ``otlp`` or
``loki_push_api``, and the collector matches rules to logs by topology.

Requirer Side (charms whose logs are filtered)
-----------------------------------------------

Publish the rules as OTTL log record conditions; a record matching any of them is dropped::

    from charmlibs.interfaces.log_filters import LogFiltersRequirer

    HEALTH_CHECKS = 'attributes["http_request.path"] != nil and IsMatch(...)'

    class MyWorkload(CharmBase):
        def _reconcile(self, _: ops.EventBase):
            LogFiltersRequirer(self, ottl_drop=[HEALTH_CHECKS]).publish()

Only the leader writes. The rules apply to every unit of the application.

Provider Side (collectors that apply the filters)
--------------------------------------------------

::

    from charmlibs.interfaces.log_filters import LogFiltersProvider

    accepted, refused = LogFiltersProvider(self).resolve_sources()
    for source, filters in accepted.items():
        ...  # a pipeline keeping only `source`'s records, then dropping `filters.ottl_drop`

Each relation's claimed topology is checked against what Juju reports, and a source claimed by
two relations stays with the older one. Topology identifies a source; it does not authenticate
the sender of a log record. The provider must check the conditions with its collector before
using them, for example with ``otelcol validate``.

Relation Data Format
====================

The requirer's app databag::

    "metadata": {
        "model": "iam",
        "model_uuid": "f4d59020-c8e7-4053-8044-a2c1e5591c7f",
        "application": "kratos",
        "unit": "kratos/0",
        "charm_name": "kratos"
    }
    "filters": {
        "ottl": {"drop": ["<OTTL condition>", "..."]}
    }

``filters`` is keyed by rule language, as the ``otlp`` interface keys its rules by query
language; a provider ignores languages it does not support. The provider writes nothing.
"""

from ._log_filters import (
    MAX_CONDITION_LENGTH,
    MAX_CONDITIONS,
    LogFiltersProvider,
    LogFiltersRequirer,
    Source,
    SourceFilters,
)
from ._version import __version__ as __version__

__all__ = [
    'MAX_CONDITIONS',
    'MAX_CONDITION_LENGTH',
    'LogFiltersProvider',
    'LogFiltersRequirer',
    'Source',
    'SourceFilters',
]
