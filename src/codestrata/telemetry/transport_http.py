"""HTTP transport surface re-exports (Slice 9.11)."""

from __future__ import annotations

from codestrata.telemetry.infrastructure.http_client import (
    FakeTelemetryHttpClient,
    FakeTelemetryHttpResponse,
    StdlibTelemetryHttpClient,
    TelemetryHttpClient,
    TelemetryHttpResponse,
)
from codestrata.telemetry.infrastructure.http_transport import HttpTelemetryTransport
from codestrata.telemetry.transport_factory import create_http_telemetry_transport

__all__ = [
    "FakeTelemetryHttpClient",
    "FakeTelemetryHttpResponse",
    "HttpTelemetryTransport",
    "StdlibTelemetryHttpClient",
    "TelemetryHttpClient",
    "TelemetryHttpResponse",
    "create_http_telemetry_transport",
]
