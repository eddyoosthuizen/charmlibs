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

"""Unit tests for forward_logs_over_otlp and plan_contains_layer."""

import json
from typing import Any
from unittest import mock

import ops
from ops import pebble, testing
from scenario.mocking import _MockPebbleClient

from charmlibs.interfaces.log_filters import forward_logs_over_otlp, plan_contains_layer

MODEL_UUID = '11111111-1111-4111-8111-111111111111'
ENDPOINT = 'https://log-aggregator.example:4318'
# Fixed, because testing.State otherwise draws a new model, and so new topology labels, each run.
MODEL = testing.Model(name='iam', uuid=MODEL_UUID)
COS_TARGET = {
    'override': 'replace',
    'type': 'loki',
    'location': 'http://loki:3100/loki/api/v1/push',
    'services': ['all'],
    'labels': {'product': 'Juju'},
}


ADD_LAYER = ops.Container.add_layer


class WorkloadCharm(ops.CharmBase):
    reason: str | None = None

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on.update_status, self._forward)

    def _forward(self, _: ops.EventBase) -> None:
        WorkloadCharm.reason = forward_logs_over_otlp(self, self.unit.get_container('workload'))


def context() -> testing.Context[WorkloadCharm]:
    meta: dict[str, Any] = {
        'name': 'kratos',
        'containers': {'workload': {}},
        'requires': {'send-otlp-logs': {'interface': 'otlp'}},
    }
    return testing.Context(WorkloadCharm, meta=meta)


def otlp_relation(relation_id: int) -> testing.Relation:
    endpoints = [{'protocol': 'http', 'endpoint': ENDPOINT, 'telemetries': ['logs', 'metrics']}]
    return testing.Relation(
        'send-otlp-logs', id=relation_id, remote_app_data={'endpoints': json.dumps(endpoints)}
    )


def workload(log_targets: dict[str, Any] | None = None) -> testing.Container:
    layers = {'cos': pebble.Layer({'log-targets': log_targets})} if log_targets else {}
    return testing.Container('workload', can_connect=True, layers=layers)


def run(
    state: testing.State, pebble_version: str = '1.26.0'
) -> tuple[testing.State, mock.MagicMock]:
    """Run update-status with Pebble at `pebble_version`, recording add_layer calls."""
    ctx = context()
    info = pebble.SystemInfo(version=pebble_version)
    with (
        mock.patch.object(_MockPebbleClient, 'get_system_info', return_value=info),
        # side_effect, not wraps: Python 3.10's autospec does not pass calls through to wraps.
        mock.patch.object(
            ops.Container, 'add_layer', autospec=True, side_effect=ADD_LAYER
        ) as add_layer,
    ):
        out = ctx.run(ctx.on.update_status(), state)
    return out, add_layer


def log_targets(state: testing.State) -> dict[str, Any]:
    return state.get_container('workload').plan.to_dict().get('log-targets', {})


def test_each_relation_gets_a_target_labelled_with_the_unit_topology():
    state = testing.State(model=MODEL, relations=[otlp_relation(7)], containers=[workload()])
    out, _ = run(state)
    assert log_targets(out)['otlp-logs-7'] == {
        'type': 'opentelemetry',
        'location': ENDPOINT,
        'services': ['all'],
        'labels': {
            'juju_model': 'iam',
            'juju_model_uuid': MODEL_UUID,
            'juju_application': 'kratos',
            'juju_unit': 'kratos/0',
            'charm': 'kratos',
        },
        'override': 'replace',
    }
    assert WorkloadCharm.reason is None


def test_an_old_pebble_gets_no_target_and_a_reason():
    state = testing.State(model=MODEL, relations=[otlp_relation(7)], containers=[workload()])
    out, _ = run(state, pebble_version='v1.19.2')
    assert log_targets(out) == {}
    assert WorkloadCharm.reason is not None and 'logging' in WorkloadCharm.reason


def test_a_removed_relation_is_disabled_and_other_targets_are_left_alone():
    first, _ = run(
        testing.State(
            model=MODEL, relations=[otlp_relation(7)], containers=[workload({'cos': COS_TARGET})]
        )
    )
    out, _ = run(testing.State(model=MODEL, relations=[], containers=first.containers))
    targets = log_targets(out)
    assert targets['otlp-logs-7']['services'] == ['-all']
    assert targets['cos']['services'] == ['all']


def test_an_unchanged_plan_is_not_added_to_again():
    first, _ = run(
        testing.State(model=MODEL, relations=[otlp_relation(7)], containers=[workload()])
    )
    _, add_layer = run(
        testing.State(model=MODEL, relations=first.relations, containers=first.containers)
    )
    add_layer.assert_not_called()


def test_plan_contains_layer_compares_what_the_layer_sets():
    service: pebble.ServiceDict = {
        'override': 'replace',
        'command': 'kratos serve',
        'environment': {'DEBUG': 'true'},
    }
    check: pebble.CheckDict = {'override': 'replace', 'http': {'url': 'http://localhost/health'}}
    planned = pebble.Layer({'services': {'kratos': service}, 'checks': {'up': check}})
    container = testing.Container('workload', can_connect=True, layers={'base': planned})
    ctx = context()
    state = testing.State(containers=[container])
    with ctx(ctx.on.update_status(), state) as manager:
        workload_container = manager.charm.unit.get_container('workload')
        assert plan_contains_layer(workload_container, planned)
        changed: pebble.LayerDict = {
            'services': {'kratos': {**service, 'command': 'kratos migrate'}}
        }
        assert not plan_contains_layer(workload_container, pebble.Layer(changed))
