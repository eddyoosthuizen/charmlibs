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

"""Forward a container's Pebble service logs to the endpoints of an ``otlp`` relation.

Separate from the log_filters interface: it reads the ``otlp`` interface as published, and
configures Pebble's ``opentelemetry`` log targets, which need Pebble 1.24 or later.
"""

import re
from typing import Any, cast

import ops
from cosl.juju_topology import JujuTopology
from ops.pebble import Layer, LayerDict

from charmlibs.interfaces.otlp import OtlpRequirer

DEFAULT_OTLP_RELATION_NAME = 'send-otlp-logs'
OTLP_TARGET_MIN_PEBBLE = (1, 24)
TARGET_PREFIX = 'otlp-logs-'

_LAYER_SECTIONS = ('services', 'checks', 'log-targets')
# Pebble prints a check's default threshold into the plan even when the layer sets none.
_PEBBLE_DEFAULTED_KEYS = frozenset({'threshold'})


def forward_logs_over_otlp(
    charm: ops.CharmBase,
    container: ops.Container,
    relation_name: str = DEFAULT_OTLP_RELATION_NAME,
) -> str | None:
    """Make the container's Pebble forward every service's logs to each related endpoint.

    One ``opentelemetry`` log target per relation, labelled with this unit's Juju topology. A
    removed relation's target is disabled, since Pebble cannot delete one; targets this function
    did not create are left alone. The layer is only added when the plan does not already hold
    it, because before Pebble 1.33 every ``add_layer`` resends forwarded services' log buffers.

    The ``otlp`` relation is only read: this never publishes to it, because
    ``OtlpRequirer.publish()`` would also send generic alert rules for this application.

    Call it from the charm's reconcile, for each container whose logs should be forwarded.

    Returns:
        None when the targets match the relations, otherwise why logs cannot be forwarded,
        for the charm to show in its status.
    """
    if not container.can_connect():
        return f'cannot connect to Pebble in container {container.name}'
    endpoints = OtlpRequirer(
        charm, relation_name, protocols=['http'], telemetries=['logs']
    ).endpoints
    pebble_version = container.pebble.get_system_info().version
    supported = _is_at_least(pebble_version, OTLP_TARGET_MIN_PEBBLE)
    targets: dict[str, dict[str, Any]] = {}
    if supported:
        labels = _topology_labels(JujuTopology.from_charm(charm))
        for relation_id, endpoint in sorted(endpoints.items()):
            targets[f'{TARGET_PREFIX}{relation_id}'] = {
                'override': 'replace',
                'type': 'opentelemetry',
                'location': endpoint.endpoint,
                'services': ['all'],
                'labels': labels,
            }
    planned = cast('dict[str, Any]', container.get_plan().to_dict()).get('log-targets', {})
    for name, target in sorted(planned.items()):
        if not name.startswith(TARGET_PREFIX) or name in targets:
            continue
        if target.get('services') == ['-all']:
            continue
        targets[name] = {
            'override': 'replace',
            'type': target['type'],
            'location': target['location'],
            'services': ['-all'],
        }
    if targets:
        layer = Layer(cast('LayerDict', {'log-targets': targets}))
        if not plan_contains_layer(container, layer):
            container.add_layer(f'{container.name}-otlp-logs', layer, combine=True)
    if endpoints and not supported:
        return (
            f'Pebble {pebble_version} cannot forward logs over OTLP (needs 1.24 or later); '
            'relate the logging endpoint instead'
        )
    return None


def plan_contains_layer(container: ops.Container, layer: Layer | LayerDict) -> bool:
    """Report whether the container's plan already holds everything ``layer`` would set.

    Pebble announces a plan change for every ``add_layer``, even an identical one, and before
    v1.33 each announcement makes it resend every forwarded service's log buffer. Callers skip
    ``add_layer`` when this returns True. Any difference, or an entry this cannot compare,
    returns False, which only costs the ``add_layer`` that was always made.
    """
    layer_obj = layer if isinstance(layer, Layer) else Layer(layer)
    layer_dict = cast('dict[str, Any]', layer_obj.to_dict())
    plan_dict = cast('dict[str, Any]', container.get_plan().to_dict())
    for section in _LAYER_SECTIONS:
        for name, entry in layer_dict.get(section, {}).items():
            planned_entry = plan_dict.get(section, {}).get(name)
            if not isinstance(planned_entry, dict):
                return False
            expected = {key: value for key, value in entry.items() if key != 'override'}
            if 'environment' in expected:
                # Pebble stores a service's environment as strings, YAML-style for booleans.
                expected['environment'] = {
                    key: str(value).lower() if isinstance(value, bool) else str(value)
                    for key, value in expected['environment'].items()
                }
            actual = {
                key: value
                for key, value in cast('dict[str, Any]', planned_entry).items()
                if key != 'override' and (key in expected or key not in _PEBBLE_DEFAULTED_KEYS)
            }
            if actual != expected:
                return False
    return True


def _topology_labels(topology: JujuTopology) -> dict[str, str]:
    # LogForwarder's label names, so one query finds a workload's lines in COS and elsewhere.
    # Never its "product" label: LogForwarder treats targets carrying it as its own.
    return {
        'juju_model': topology.model,
        'juju_model_uuid': topology.model_uuid,
        'juju_application': topology.application,
        'juju_unit': topology.unit or '',
        'charm': topology.charm_name or '',
    }


def _is_at_least(version: str, minimum: tuple[int, int]) -> bool:
    found = re.match(r'v?(\d+)\.(\d+)', version.strip())
    return found is not None and (int(found[1]), int(found[2])) >= minimum
