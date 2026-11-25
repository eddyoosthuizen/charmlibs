# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""This file defines the schemas for the provider and requirer sides of this relation interface.

Examples:
    RequirerAppData:
        {
            "metadata": {
                "model": "iam",
                "model_uuid": "f4d59020-c8e7-4053-8044-a2c1e5591c7f",
                "application": "kratos",
                "unit": "kratos/0",
                "charm_name": "kratos"
            },
            "filters": {
                "ottl": {"drop": ["attributes[\"http_request.path\"] == \"/health/ready\""]}
            }
        }

The provider never writes to its databags.
"""

from pydantic import BaseModel, Field


class MetadataSchema(BaseModel):
    """The requirer's Juju topology, as cosl's JujuTopology.as_dict() gives it."""

    model: str
    model_uuid: str
    application: str
    unit: str
    charm_name: str


class OttlFiltersSchema(BaseModel):
    """OTTL log record conditions; a record matching any of them is dropped."""

    drop: list[str] = Field(default_factory=list, max_length=50)


class FiltersSchema(BaseModel):
    """Rule sets keyed by language. Providers ignore languages they do not support."""

    ottl: OttlFiltersSchema | None = None


class RequirerAppData(BaseModel):
    """Application databag model for the requirer side of this interface."""

    metadata: MetadataSchema = Field(
        description="Juju topology of the charm whose logs these filter."
    )
    filters: FiltersSchema = Field(description="Rule sets keyed by language.")


ProviderAppData = None
ProviderUnitData = None
RequirerUnitData = None
