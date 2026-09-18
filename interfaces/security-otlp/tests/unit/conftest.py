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

"""Fixtures and test charms shared by the security-otlp unit tests."""

import ops
import pytest
from ops import testing
from ops.charm import CharmBase

from charmlibs.interfaces.security_otlp import SecurityOtlpProvider
from charmlibs.interfaces.security_otlp._security_otlp import (
    DEFAULT_PROVIDER_RELATION_NAME,
    DEFAULT_REQUIRER_RELATION_NAME,
)

PROVIDER_ENDPOINT_PROTOCOL = 'http'
PROVIDER_ENDPOINT_URL = 'https://collector.example:4318'


class SecurityOtlpProviderCharm(CharmBase):
    """A minimal charm that publishes one security-otlp endpoint on update-status."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.framework.observe(self.on.update_status, self._publish_endpoint)

    def _publish_endpoint(self, _: ops.EventBase) -> None:
        SecurityOtlpProvider(self).add_endpoint(
            protocol=PROVIDER_ENDPOINT_PROTOCOL, endpoint=PROVIDER_ENDPOINT_URL
        ).publish()


class SecurityOtlpRequirerCharm(CharmBase):
    """A minimal charm used only to obtain a live charm instance for requirer tests."""


@pytest.fixture
def security_otlp_provider_ctx() -> testing.Context[SecurityOtlpProviderCharm]:
    meta = {
        'name': 'security-otlp-provider',
        'provides': {DEFAULT_PROVIDER_RELATION_NAME: {'interface': 'security_otlp'}},
    }
    return testing.Context(SecurityOtlpProviderCharm, meta=meta)


@pytest.fixture
def security_otlp_requirer_ctx() -> testing.Context[SecurityOtlpRequirerCharm]:
    meta = {
        'name': 'security-otlp-requirer',
        'requires': {DEFAULT_REQUIRER_RELATION_NAME: {'interface': 'security_otlp'}},
    }
    return testing.Context(SecurityOtlpRequirerCharm, meta=meta)
