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

"""Internal implementation of the log_filters Provider and Requirer library.

This document is the authoritative reference on the structure of relation data that is
shared between charms that publish log filters and charms that apply them.
For user-facing documentation, see the package-level docstring in __init__.py.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import ops
from cosl.juju_topology import JujuTopology
from pydantic import BaseModel, Field, field_validator

DEFAULT_REQUIRER_RELATION_NAME = 'send-log-filters'
DEFAULT_PROVIDER_RELATION_NAME = 'receive-log-filters'
MAX_CONDITIONS = 50
MAX_CONDITION_LENGTH = 2000

logger = logging.getLogger(__name__)


class _Metadata(BaseModel):
    """The requirer's Juju topology, in the shape of cosl's ``JujuTopology.as_dict()``."""

    model: str
    model_uuid: str = Field(min_length=1)
    application: str = Field(min_length=1)
    unit: str
    charm_name: str


class _OttlFilters(BaseModel):
    """OTTL log record conditions; a record matching any of them is dropped."""

    drop: list[str] = Field(default_factory=list[str], max_length=MAX_CONDITIONS)

    @field_validator('drop')
    @classmethod
    def _check_conditions(cls, drop: list[str]) -> list[str]:
        for condition in drop:
            if not condition.strip():
                raise ValueError('every condition must be a non-empty string')
            if len(condition) > MAX_CONDITION_LENGTH or not condition.isprintable():
                raise ValueError(
                    f'a condition must be printable and at most {MAX_CONDITION_LENGTH} characters'
                )
        return drop


class _Filters(BaseModel):
    """Rule sets keyed by language. Unknown languages are ignored, so new ones can be added."""

    ottl: _OttlFilters | None = None


class _RequirerAppData(BaseModel):
    """A pydantic model for the log_filters requirer's app databag."""

    metadata: _Metadata = Field(description='Juju topology of the charm whose logs these filter.')
    filters: _Filters = Field(description='Rule sets keyed by language.')


@dataclass(frozen=True, order=True)
class Source:
    """The logs a rule set applies to: every unit of one application in one model."""

    model_uuid: str
    application: str


@dataclass(frozen=True)
class SourceFilters:
    """One accepted relation's rules.

    Attributes:
        relation_id: The relation the rules came from.
        ottl_drop: OTTL log record conditions; a record matching any of them is dropped.
        claim_checked: False when Juju could not report the remote model (before Juju 3.6.2),
            so the claimed topology was taken as given.
    """

    relation_id: int
    ottl_drop: tuple[str, ...]
    claim_checked: bool


class LogFiltersRequirer:
    """Publishes a charm's log filters and Juju topology to every related provider.

    Args:
        charm: The charm instance.
        relation_name: The name of the relation to use.
        ottl_drop: OTTL log record conditions; a record matching any of them is dropped.
    """

    def __init__(
        self,
        charm: ops.CharmBase,
        relation_name: str = DEFAULT_REQUIRER_RELATION_NAME,
        *,
        ottl_drop: Sequence[str] = (),
    ):
        self._charm = charm
        self._relation_name = relation_name
        self._ottl_drop = list(ottl_drop)

    def publish(self) -> None:
        """Write the filters and topology to every relation's app databag, from the leader.

        Raises:
            pydantic.ValidationError: if a condition is empty, too long or unprintable, or there
                are more than ``MAX_CONDITIONS``. The conditions come from the charm's own code,
                so this is a bug in the charm, not a runtime condition.
        """
        if not self._charm.unit.is_leader():
            return
        databag = _RequirerAppData(
            metadata=_Metadata.model_validate(JujuTopology.from_charm(self._charm).as_dict()),
            filters=_Filters(ottl=_OttlFilters(drop=self._ottl_drop)),
        )
        for relation in self._charm.model.relations[self._relation_name]:
            relation.save(databag, self._charm.app)


class LogFiltersProvider:
    """Reads the log filters that related requirers publish.

    Args:
        charm: The charm instance.
        relation_name: The name of the relation to use.
    """

    def __init__(self, charm: ops.CharmBase, relation_name: str = DEFAULT_PROVIDER_RELATION_NAME):
        self._charm = charm
        self._relation_name = relation_name

    def resolve_sources(self) -> tuple[dict[Source, SourceFilters], dict[int, str]]:
        """Each relation's source, from the topology it claims, and the relations refused.

        The claim is checked against what Juju reports: the model UUID, where Juju can report
        it, and the application name when the relation is within this model (across models
        Juju shows an alias). Topology identifies a source; it does not authenticate it. If two
        relations claim one source, the older relation keeps it, so relating later cannot take
        over a source. Relations whose requirer has not published yet are skipped.

        Returns:
            The accepted sources, and a reason for each refused relation ID.
        """
        accepted: dict[Source, SourceFilters] = {}
        owners: dict[Source, int] = {}
        refused: dict[int, str] = {}
        relations = sorted(self._charm.model.relations[self._relation_name], key=lambda r: r.id)
        for relation in relations:
            if not relation.data[relation.app]:
                continue
            try:
                data = relation.load(_RequirerAppData, relation.app)
            except ValueError as e:
                refused[relation.id] = f'relation data failed validation: {e}'
                continue
            source = Source(data.metadata.model_uuid, data.metadata.application)
            try:
                remote_model_uuid: str | None = relation.remote_model.uuid
            except ops.ModelError:
                remote_model_uuid = None
            if remote_model_uuid is not None and source.model_uuid != remote_model_uuid:
                refused[relation.id] = 'metadata names another model than Juju reports'
            elif (
                remote_model_uuid == self._charm.model.uuid
                and source.application != relation.app.name
            ):
                refused[relation.id] = 'metadata names another application than Juju reports'
            elif source in owners:
                refused[relation.id] = f'relation {owners[source]} already claims this source'
            else:
                owners[source] = relation.id
                ottl = data.filters.ottl
                accepted[source] = SourceFilters(
                    relation_id=relation.id,
                    ottl_drop=tuple(ottl.drop) if ottl else (),
                    claim_checked=remote_model_uuid is not None,
                )
                if remote_model_uuid is None:
                    logger.warning(
                        'relation %d: Juju cannot report the remote model, so the claimed '
                        'topology is unchecked',
                        relation.id,
                    )
        for relation_id, reason in refused.items():
            logger.warning('relation %d refused: %s', relation_id, reason)
        return accepted, refused
