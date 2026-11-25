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

"""Unit tests for the log_filters requirer and provider."""

import json
from typing import Any

import ops
import pydantic
import pytest
from ops import testing

from charmlibs.interfaces.log_filters import LogFiltersProvider, LogFiltersRequirer, Source

OWN_MODEL = '11111111-1111-4111-8111-111111111111'
OTHER_MODEL = '22222222-2222-4222-8222-222222222222'
HEALTH_CHECKS = 'attributes["http_request.path"] == "/health/ready"'


class WorkloadCharm(ops.CharmBase):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on.update_status, self._publish)

    def _publish(self, _: ops.EventBase) -> None:
        LogFiltersRequirer(self, ottl_drop=[HEALTH_CHECKS]).publish()


class CollectorCharm(ops.CharmBase):
    pass


def requirer_context() -> testing.Context[WorkloadCharm]:
    meta: dict[str, Any] = {
        'name': 'kratos',
        'requires': {'send-log-filters': {'interface': 'log_filters'}},
    }
    return testing.Context(WorkloadCharm, meta=meta)


def provider_context(juju_version: str = '3.6.13') -> testing.Context[CollectorCharm]:
    meta: dict[str, Any] = {
        'name': 'log-aggregator',
        'provides': {'receive-log-filters': {'interface': 'log_filters'}},
    }
    return testing.Context(CollectorCharm, meta=meta, juju_version=juju_version)


def published(
    model_uuid: str, application: str, filters: dict[str, Any] | None = None
) -> dict[str, str]:
    """A requirer's app databag as LogFiltersRequirer writes it."""
    metadata = {
        'model': 'iam',
        'model_uuid': model_uuid,
        'application': application,
        'unit': f'{application}/0',
        'charm_name': application,
    }
    rules = filters if filters is not None else {'ottl': {'drop': [HEALTH_CHECKS]}}
    return {'metadata': json.dumps(metadata), 'filters': json.dumps(rules)}


def source_relation(
    relation_id: int, remote_app: str, remote_model: str, data: dict[str, str]
) -> testing.Relation:
    return testing.Relation(
        'receive-log-filters',
        id=relation_id,
        remote_app_name=remote_app,
        remote_app_data=data,
        remote_model_uuid=remote_model,
    )


def resolve(
    ctx: testing.Context[CollectorCharm], relations: list[testing.Relation]
) -> tuple[dict[Source, Any], dict[int, str]]:
    state = testing.State(model=testing.Model(uuid=OWN_MODEL), relations=relations)
    with ctx(ctx.on.update_status(), state) as manager:
        return LogFiltersProvider(manager.charm).resolve_sources()


def test_the_leader_publishes_its_rules_and_topology():
    ctx = requirer_context()
    relation = testing.Relation('send-log-filters')
    state = testing.State(
        leader=True, model=testing.Model(name='iam', uuid=OWN_MODEL), relations=[relation]
    )
    out = ctx.run(ctx.on.update_status(), state)
    databag = out.get_relation(relation.id).local_app_data
    assert json.loads(databag['filters']) == {'ottl': {'drop': [HEALTH_CHECKS]}}
    metadata = json.loads(databag['metadata'])
    assert (metadata['model_uuid'], metadata['application']) == (OWN_MODEL, 'kratos')


def test_a_follower_publishes_nothing():
    ctx = requirer_context()
    relation = testing.Relation('send-log-filters')
    out = ctx.run(ctx.on.update_status(), testing.State(leader=False, relations=[relation]))
    assert out.get_relation(relation.id).local_app_data == {}


def test_a_badly_formed_condition_is_a_charm_bug():
    ctx = requirer_context()
    state = testing.State(leader=True, relations=[testing.Relation('send-log-filters')])
    with ctx(ctx.on.update_status(), state) as manager:
        with pytest.raises(pydantic.ValidationError):
            LogFiltersRequirer(manager.charm, ottl_drop=['  ']).publish()


def test_a_claim_juju_confirms_is_accepted():
    same_model = source_relation(3, 'kratos', OWN_MODEL, published(OWN_MODEL, 'kratos'))
    cross_model = source_relation(4, 'remote-0a1b2c', OTHER_MODEL, published(OTHER_MODEL, 'hydra'))
    accepted, refused = resolve(provider_context(), [same_model, cross_model])
    assert refused == {}
    kratos = accepted[Source(OWN_MODEL, 'kratos')]
    assert (kratos.relation_id, kratos.ottl_drop, kratos.claim_checked) == (
        3,
        (HEALTH_CHECKS,),
        True,
    )
    assert accepted[Source(OTHER_MODEL, 'hydra')].relation_id == 4


def test_a_claim_juju_contradicts_is_refused():
    wrong_model = source_relation(3, 'wordpress', OWN_MODEL, published(OTHER_MODEL, 'wordpress'))
    wrong_app = source_relation(4, 'wordpress', OWN_MODEL, published(OWN_MODEL, 'kratos'))
    accepted, refused = resolve(provider_context(), [wrong_model, wrong_app])
    assert accepted == {}
    assert set(refused) == {3, 4}


def test_a_second_claim_on_a_source_is_refused_whichever_order_juju_lists_them():
    newer = source_relation(9, 'remote-bbbb', OTHER_MODEL, published(OTHER_MODEL, 'kratos'))
    older = source_relation(3, 'remote-aaaa', OTHER_MODEL, published(OTHER_MODEL, 'kratos'))
    accepted, refused = resolve(provider_context(), [newer, older])
    assert accepted[Source(OTHER_MODEL, 'kratos')].relation_id == 3
    assert set(refused) == {9}


def test_before_juju_3_6_2_the_claim_is_accepted_unchecked():
    relation = source_relation(3, 'remote-aaaa', OTHER_MODEL, published(OWN_MODEL, 'anything'))
    accepted, _ = resolve(provider_context(juju_version='3.6.1'), [relation])
    assert accepted[Source(OWN_MODEL, 'anything')].claim_checked is False


def test_invalid_relation_data_is_refused_and_unknown_languages_are_ignored():
    too_many = published(OWN_MODEL, 'kratos', {'ottl': {'drop': ['true'] * 51}})
    no_metadata = {'filters': json.dumps({'ottl': {'drop': []}})}
    other_language = published(OTHER_MODEL, 'hydra', {'vrl': {'drop': ['.x == 1']}})
    accepted, refused = resolve(
        provider_context(),
        [
            source_relation(3, 'kratos', OWN_MODEL, too_many),
            source_relation(4, 'kratos', OWN_MODEL, no_metadata),
            source_relation(5, 'remote-cccc', OTHER_MODEL, other_language),
        ],
    )
    assert set(refused) == {3, 4}
    assert accepted[Source(OTHER_MODEL, 'hydra')].ottl_drop == ()


def test_a_requirer_that_has_not_published_is_skipped():
    relation = source_relation(3, 'kratos', OWN_MODEL, {})
    assert resolve(provider_context(), [relation]) == ({}, {})
