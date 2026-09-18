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

"""security-otlp Provider and Requirer Library.

security-otlp lets a workload charm send a security-relevant, logs-only subset of its
telemetry directly to a purpose-built collector, bypassing its general `otlp`/COS pipeline for
this one class of data.

Getting Started
================

Provider Side (log-aggregator-k8s: offering a security-otlp endpoint)
-----------------------------------------------------------------------

To provide a security-otlp endpoint, use the ``SecurityOtlpProvider`` class. Add and publish
endpoints with ``add_endpoint`` and ``publish()``::

    from charmlibs.interfaces.security_otlp import SecurityOtlpProvider

    class MyCollector(CharmBase):
        def __init__(self, *args):
            super().__init__(*args)
            self.framework.observe(self.on.ingress_ready, self._publish_endpoint)

        def _publish_endpoint(self, event):
            SecurityOtlpProvider(self).add_endpoint(
                protocol="http",
                endpoint="https://log-aggregator.secops.example:4318",
            ).publish()

Every endpoint published on this interface must use ``https://`` -- ``add_endpoint`` raises
``ValueError`` immediately if it doesn't, rather than silently accepting a plaintext endpoint.

Requirer Side (hydra, kratos: consuming a security-otlp endpoint)
---------------------------------------------------------------------

To consume a security-otlp endpoint, use the ``SecurityOtlpRequirer`` class::

    from charmlibs.interfaces.security_otlp import SecurityOtlpRequirer

    class MySourceCharm(CharmBase):
        def __init__(self, framework):
            super().__init__(framework)
            self.framework.observe(self.on.update_status, self._access_endpoint)

        def _access_endpoint(self, _):
            endpoints = SecurityOtlpRequirer(self, protocols=["http", "grpc"]).endpoints

If a provider offers more than one supported protocol, the requirer prefers ``grpc`` over
``http``. There is no requirer-side ``publish()`` -- this interface carries no rules, so the
requirer only ever reads.

Relation Data Format
=====================

The provider publishes a list of endpoints under the ``endpoints`` key::

    "endpoints": [
        {
            "protocol": "http",
            "endpoint": "https://log-aggregator.secops.example:4318"
        }
    ]

There is no ``telemetries`` key (every endpoint on this interface is implicitly logs-only) and
no ``insecure`` key (every endpoint is TLS-secured by construction).
"""

from ._security_otlp import (
    SecurityOtlpEndpoint,
    SecurityOtlpProvider,
    SecurityOtlpRequirer,
)
from ._version import __version__ as __version__

__all__ = [
    # only the names listed in __all__ are imported when executing:
    # from charmlibs.interfaces.security_otlp import *
    'SecurityOtlpEndpoint',
    'SecurityOtlpProvider',
    'SecurityOtlpRequirer',
]
