# Changelog

All notable changes to the charmlibs.interfaces.security_otlp library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

### Added

- Initial release of charmlibs.interfaces.security_otlp
- `SecurityOtlpRequirer` for consuming a security-otlp endpoint from a provider relation
- `SecurityOtlpProvider` for publishing a security-otlp endpoint to requirer relations
- `SecurityOtlpEndpoint` pydantic model representing a single security-otlp endpoint (protocol, URL)
- Support for filtering endpoints by protocol (`http`, `grpc`); `gRPC` is favoured over `HTTP` when
  multiple endpoints are available
- `SecurityOtlpProvider.add_endpoint()` rejects a non-`https://` endpoint immediately, since TLS is
  required on this interface from the first release
- Logs-only by design: no `telemetries` filter, and no requirer-side `publish()`, since this
  interface carries no rules
- Python 3.10+ compatibility
