# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Feature: security-otlp endpoint handling."""

import json
from collections.abc import Sequence
from typing import Literal

import ops
import pytest
from conftest import PROVIDER_ENDPOINT_PROTOCOL, PROVIDER_ENDPOINT_URL
from ops import testing
from ops.testing import Relation, State

from charmlibs.interfaces.security_otlp import (
    SecurityOtlpEndpoint,
    SecurityOtlpProvider,
    SecurityOtlpRequirer,
)
from charmlibs.interfaces.security_otlp._security_otlp import (
    DEFAULT_PROVIDER_RELATION_NAME as RECEIVE,
)
from charmlibs.interfaces.security_otlp._security_otlp import (
    DEFAULT_REQUIRER_RELATION_NAME as SEND,
)
from charmlibs.interfaces.security_otlp._security_otlp import (
    _SecurityOtlpEndpoint,
    _SecurityOtlpProviderAppData,
)

HTTP_ENDPOINT = _SecurityOtlpEndpoint(protocol='http', endpoint='https://a.example:4318')
GRPC_ENDPOINT = _SecurityOtlpEndpoint(protocol='grpc', endpoint='https://b.example:4317')
WEBSOCKET_ENDPOINT = _SecurityOtlpEndpoint(protocol='websocket', endpoint='https://c.example:4319')


def test_new_endpoint_key_is_ignored_by_databag_model():
    # GIVEN a raw endpoint dict with an extra, unrecognized key
    endpoint = {
        'protocol': 'http',
        'endpoint': 'https://collector.example:4318',
        'unexpected_key': 'value',
    }

    # WHEN it is validated into the provider's databag model
    provider_databag = _SecurityOtlpProviderAppData.model_validate({'endpoints': [endpoint]})

    # THEN validation succeeds and the unrecognized key is dropped, not rejected
    assert 'unexpected_key' not in provider_databag.endpoints[0].model_dump()


def test_add_endpoint_rejects_non_https(
    security_otlp_provider_ctx: testing.Context[ops.CharmBase],
):
    ctx = security_otlp_provider_ctx
    with ctx(ctx.on.update_status(), state=State()) as mgr:
        provider = SecurityOtlpProvider(mgr.charm)

        # GIVEN a plaintext endpoint
        # WHEN it is added to the provider
        # THEN a ValueError is raised immediately
        with pytest.raises(ValueError):
            provider.add_endpoint(protocol='http', endpoint='http://insecure.example:4318')

        # AND nothing was appended to the provider's endpoint list
        assert provider._endpoints == []


def test_add_endpoint_accepts_https_and_chains(
    security_otlp_provider_ctx: testing.Context[ops.CharmBase],
):
    ctx = security_otlp_provider_ctx
    with ctx(ctx.on.update_status(), state=State()) as mgr:
        provider = SecurityOtlpProvider(mgr.charm)

        # GIVEN two valid, chained add_endpoint calls
        result = provider.add_endpoint(
            protocol='http', endpoint='https://a.example:4318'
        ).add_endpoint(protocol='grpc', endpoint='https://b.example:4317')

        # THEN add_endpoint returns the same provider object, enabling chaining
        assert result is provider
        # AND both endpoints were recorded, in the order they were added
        assert provider._endpoints == [HTTP_ENDPOINT, GRPC_ENDPOINT]


def test_publish_skips_non_leader(security_otlp_provider_ctx: testing.Context[ops.CharmBase]):
    # GIVEN a non-leader unit with a connected relation
    state = State(leader=False, relations=[Relation(RECEIVE)])

    # WHEN the charm publishes its endpoint on update-status
    state_out = security_otlp_provider_ctx.run(
        security_otlp_provider_ctx.on.update_status(), state=state
    )

    # THEN nothing was written to the relation's local app databag
    published_relation = next(iter(state_out.relations))
    assert dict(published_relation.local_app_data) == {}


def test_publish_writes_expected_databag_shape(
    security_otlp_provider_ctx: testing.Context[ops.CharmBase],
):
    # GIVEN a leader unit with two connected relations
    state = State(leader=True, relations=[Relation(RECEIVE, id=1), Relation(RECEIVE, id=2)])

    # WHEN the charm publishes its endpoint on update-status
    state_out = security_otlp_provider_ctx.run(
        security_otlp_provider_ctx.on.update_status(), state=state
    )

    # THEN every relation's local app databag has exactly the expected shape:
    # * the one published endpoint, under "endpoints"
    # * no "telemetries" key and no "insecure" key -- they don't exist on this interface
    expected_databag = {
        'endpoints': [{'protocol': PROVIDER_ENDPOINT_PROTOCOL, 'endpoint': PROVIDER_ENDPOINT_URL}]
    }
    for published_relation in state_out.relations:
        actual_databag = _SecurityOtlpProviderAppData.model_validate({
            'endpoints': json.loads(published_relation.local_app_data['endpoints'])
        }).model_dump()
        assert actual_databag == expected_databag


@pytest.mark.parametrize(
    'protocols, expected',
    [
        (['http'], [HTTP_ENDPOINT]),
        (None, []),
    ],
)
def test_filter_endpoints_drops_unsupported_protocol(
    security_otlp_requirer_ctx: testing.Context[ops.CharmBase],
    protocols: Sequence[Literal['http', 'grpc']] | None,
    expected: list[_SecurityOtlpEndpoint],
):
    ctx = security_otlp_requirer_ctx
    with ctx(ctx.on.update_status(), state=State()) as mgr:
        # GIVEN a requirer configured with the given supported protocols
        requirer = SecurityOtlpRequirer(mgr.charm, protocols=protocols)

    # WHEN filtering a list offering both http and grpc
    # THEN only endpoints matching a supported protocol survive
    assert requirer._filter_endpoints([HTTP_ENDPOINT, GRPC_ENDPOINT]) == expected


@pytest.mark.parametrize(
    'endpoints, expected_protocol',
    [
        # gRPC preferred over HTTP
        ([HTTP_ENDPOINT, GRPC_ENDPOINT], 'grpc'),
        # a lone, unranked protocol still resolves -- there's nothing to lose a comparison to
        ([WEBSOCKET_ENDPOINT], 'websocket'),
    ],
)
def test_favor_modern_endpoints(
    security_otlp_requirer_ctx: testing.Context[ops.CharmBase],
    endpoints: list[_SecurityOtlpEndpoint],
    expected_protocol: str,
):
    ctx = security_otlp_requirer_ctx
    with ctx(ctx.on.update_status(), state=State()) as mgr:
        requirer = SecurityOtlpRequirer(mgr.charm, protocols=['http', 'grpc'])

    # THEN the most modern one is chosen
    assert requirer._favor_modern_endpoints(endpoints).protocol == expected_protocol


def test_endpoints_skips_relation_with_empty_databag(
    security_otlp_requirer_ctx: testing.Context[ops.CharmBase],
):
    # GIVEN a connected relation whose provider hasn't published anything yet
    state = State(relations=[Relation(SEND, id=7)])

    ctx = security_otlp_requirer_ctx
    with ctx(ctx.on.update_status(), state=state) as mgr:
        # WHEN the requirer resolves endpoints
        endpoints = SecurityOtlpRequirer(mgr.charm, protocols=['http', 'grpc']).endpoints

    # THEN the relation is excluded entirely, not present with an empty/None value
    assert endpoints == {}


def test_endpoints_skips_relation_with_invalid_databag(
    security_otlp_requirer_ctx: testing.Context[ops.CharmBase],
):
    # GIVEN one relation whose remote databag is missing the required "endpoint" field
    bad_relation = Relation(
        SEND, id=5, remote_app_data={'endpoints': json.dumps([{'protocol': 'http'}])}
    )
    # AND one relation with a valid databag
    good_relation = Relation(
        SEND,
        id=7,
        remote_app_data={
            'endpoints': json.dumps([{'protocol': 'http', 'endpoint': 'https://a.example:4318'}])
        },
    )
    state = State(relations=[bad_relation, good_relation])

    ctx = security_otlp_requirer_ctx
    with ctx(ctx.on.update_status(), state=state) as mgr:
        # WHEN the requirer resolves endpoints
        endpoints = SecurityOtlpRequirer(mgr.charm, protocols=['http']).endpoints

    # THEN the invalid relation is dropped, not raised
    assert 5 not in endpoints
    # AND the valid relation still resolves correctly
    assert (
        endpoints[7].model_dump()
        == SecurityOtlpEndpoint(protocol='http', endpoint='https://a.example:4318').model_dump()
    )


def test_endpoints_end_to_end(security_otlp_requirer_ctx: testing.Context[ops.CharmBase]):
    # GIVEN one relation offering a protocol this requirer doesn't support
    unsupported_relation = Relation(
        SEND,
        id=1,
        remote_app_data={
            'endpoints': json.dumps([{'protocol': 'grpc', 'endpoint': 'https://a.example:4317'}])
        },
    )
    # AND one relation offering a protocol it does support
    supported_relation = Relation(
        SEND,
        id=2,
        remote_app_data={
            'endpoints': json.dumps([{'protocol': 'http', 'endpoint': 'https://b.example:4318'}])
        },
    )
    state = State(relations=[unsupported_relation, supported_relation])

    ctx = security_otlp_requirer_ctx
    with ctx(ctx.on.update_status(), state=state) as mgr:
        # WHEN a real charm resolves endpoints end-to-end
        endpoints = SecurityOtlpRequirer(mgr.charm, protocols=['http']).endpoints

    # THEN only the supported relation appears, correctly resolved
    assert {k: v.model_dump() for k, v in endpoints.items()} == {
        2: SecurityOtlpEndpoint(protocol='http', endpoint='https://b.example:4318').model_dump()
    }
