# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""This file defines the schemas for the provider and requirer sides.

It exposes two interfaces.schema_base.DataBagSchema subclasses called:
- ProviderSchema
- RequirerSchema

Examples:
    ProviderSchema:
        unit: <empty>
        app: {
            "endpoints": [
                {
                    "protocol": "http",
                    "endpoint": "https://log-aggregator.secops.example:4318"
                }
            ]
        }

    RequirerSchema:
        unit: <empty>
        app: <empty>
"""

from interface_tester.schema_base import DataBagSchema
from pydantic import BaseModel, Field


class SecurityOtlpEndpointSchema(BaseModel):
    """A single security-otlp endpoint, as published by the provider."""

    protocol: str = Field(description="Transport protocol used to send logs to this endpoint.")
    endpoint: str = Field(
        description="HTTPS URL of the endpoint (e.g. 'https://log-aggregator.secops.example:4318')."
    )


class SecurityOtlpProvider(BaseModel):
    """SecurityOtlpProvider model."""

    endpoints: list[SecurityOtlpEndpointSchema] = Field(
        description='List of security-otlp endpoints exposed by the provider.'
    )


class ProviderSchema(DataBagSchema):
    """Provider schema for security-otlp."""

    app: SecurityOtlpProvider


class RequirerSchema(DataBagSchema):
    """Requirer schema for security-otlp.

    The requirer never writes to its own app databag -- this interface carries no rules, so
    there is nothing for the requirer to publish.
    """
