"""Telemetry infrastructure adapters (Slices 9.1 / 9.11)."""

from __future__ import annotations

from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.http_client import (
    FakeTelemetryHttpClient,
    FakeTelemetryHttpResponse,
    StdlibTelemetryHttpClient,
)
from codestrata.telemetry.infrastructure.http_transport import HttpTelemetryTransport
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
    default_unavailable_transport,
)

__all__ = [
    "CaptureTelemetryTransport",
    "FakeTelemetryHttpClient",
    "FakeTelemetryHttpResponse",
    "HttpTelemetryTransport",
    "StdlibTelemetryHttpClient",
    "UnavailableTelemetryTransport",
    "default_unavailable_transport",
]
