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

"""Internal implementation of the security-otlp Provider and Requirer library.

This document is the authoritative reference on the structure of relation data that is
shared between charms that intend to provide or consume security-otlp endpoints.
For user-facing documentation, see the package-level docstring in __init__.py.
"""

import logging
from collections.abc import Sequence
from typing import Final, Literal

from ops import CharmBase
from pydantic import BaseModel, Field, ValidationError

DEFAULT_REQUIRER_RELATION_NAME = 'send-security-otlp'
DEFAULT_PROVIDER_RELATION_NAME = 'receive-security-otlp'


logger = logging.getLogger(__name__)


class SecurityOtlpEndpoint(BaseModel):
    """A pydantic model for a single security-otlp endpoint."""

    protocol: str = Field(description='Transport protocol used to send logs to this endpoint.')
    endpoint: str = Field(description="HTTPS URL of the endpoint (e.g. 'https://collector:4318').")


class _SecurityOtlpEndpoint(SecurityOtlpEndpoint):
    """A pydantic model for a single security-otlp endpoint."""


class _SecurityOtlpProviderAppData(BaseModel):
    """A pydantic model for the security-otlp provider's app databag."""

    endpoints: list[_SecurityOtlpEndpoint] = Field(
        description='List of security-otlp endpoints exposed by the provider.'
    )


class SecurityOtlpRequirer:
    """A class for consuming security-otlp endpoints.

    Args:
        charm: The charm instance.
        relation_name: The name of the relation to use.
        protocols: The protocols to filter for in the provider's security-otlp
            endpoints.
    """

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = DEFAULT_REQUIRER_RELATION_NAME,
        protocols: Sequence[Literal['http', 'grpc']] | None = None,
    ):
        self._charm = charm
        self._relation_name = relation_name
        self._protocols: list[Literal['http', 'grpc']] = (
            list(protocols) if protocols is not None else []
        )

    def _filter_endpoints(
        self, endpoints: list[_SecurityOtlpEndpoint]
    ) -> list[_SecurityOtlpEndpoint]:
        """Filter out endpoints whose protocol isn't supported by this requirer."""
        return [e for e in endpoints if e.protocol in self._protocols]

    def _favor_modern_endpoints(
        self, endpoints: list[_SecurityOtlpEndpoint]
    ) -> _SecurityOtlpEndpoint:
        """Return the preferred endpoint using protocol priority.

        Modern protocols receive higher priority.
        Protocol ranking is `grpc` > `http`; unknown protocols rank lowest.
        """
        modern_score: Final = {'grpc': 2, 'http': 1}
        return max(endpoints, key=lambda e: modern_score.get(e.protocol, 0))

    @property
    def endpoints(self) -> dict[int, SecurityOtlpEndpoint]:
        """A mapping of relation ID to security-otlp endpoint.

        For each remote's list of endpoints, the requirer filters out endpoints with
        unsupported protocols. If multiple compatible endpoints remain, the requirer
        prefers newer protocols (`grpc` over `http`). Unknown protocols are treated as
        the lowest priority.
        """
        endpoint_map: dict[int, SecurityOtlpEndpoint] = {}
        for relation in self._charm.model.relations[self._relation_name]:
            if not relation.data[relation.app]:
                # The databag hasn't initialized yet, continue
                continue

            try:
                provider = relation.load(_SecurityOtlpProviderAppData, relation.app)
            except ValidationError as e:
                logger.error('security-otlp databag failed validation: %s', e)
                continue
            if endpoints := self._filter_endpoints(provider.endpoints):
                endpoint_map[relation.id] = self._favor_modern_endpoints(endpoints)

        return endpoint_map


class SecurityOtlpProvider:
    """A class for publishing security-otlp endpoints.

    Args:
        charm: The charm instance.
        relation_name: The name of the relation to use.
    """

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = DEFAULT_PROVIDER_RELATION_NAME,
    ):
        self._charm = charm
        self._relation_name = relation_name
        self._endpoints: list[_SecurityOtlpEndpoint] = []

    def add_endpoint(
        self,
        protocol: Literal['http', 'grpc'],
        endpoint: str,
    ) -> 'SecurityOtlpProvider':
        """Add a security-otlp endpoint to the list of endpoints to publish."""
        if not endpoint.startswith('https://'):
            raise ValueError(f'security-otlp endpoints must use TLS (https://), got: {endpoint!r}')
        self._endpoints.append(_SecurityOtlpEndpoint(protocol=protocol, endpoint=endpoint))
        return self

    def publish(self) -> None:
        """Trigger programmatic update of the relation data."""
        if not self._charm.unit.is_leader():
            # Only the leader unit can write to app data.
            return

        databag = _SecurityOtlpProviderAppData.model_validate({'endpoints': self._endpoints})
        for relation in self._charm.model.relations[self._relation_name]:
            relation.save(databag, self._charm.app)
