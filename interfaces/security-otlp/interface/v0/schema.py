# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""This file defines the schemas for the provider and requirer sides of this relation interface.

Examples:
    ProviderAppData:
        {
            "endpoints": [
                {
                    "protocol": "http",
                    "endpoint": "https://log-aggregator.secops.example:4318"
                }
            ]
        }

The requirer never writes to its databags: this interface carries no rules, so there is
nothing for the requirer to publish.
"""

from pydantic import BaseModel, Field


class SecurityOtlpEndpointSchema(BaseModel):
    """A single security-otlp endpoint, as published by the provider."""

    protocol: str = Field(description="Transport protocol used to send logs to this endpoint.")
    endpoint: str = Field(
        description="HTTPS URL of the endpoint (e.g. 'https://log-aggregator.secops.example:4318')."
    )


class ProviderAppData(BaseModel):
    """Application databag model for the provider side of this interface."""

    endpoints: list[SecurityOtlpEndpointSchema] = Field(
        description='List of security-otlp endpoints exposed by the provider.'
    )


ProviderUnitData = None
RequirerAppData = None
RequirerUnitData = None
