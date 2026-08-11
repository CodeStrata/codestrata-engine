"""HTTP telemetry transport factory (Slice 9.11 / 17.18).

Never reads environment variables here. Product command-session construction
may inject the result after explicit opt-in via ``product_transport``.
``create_default_telemetry_runtime()`` does not call this factory.
"""

from __future__ import annotations

from codestrata.telemetry.infrastructure.http_client import TelemetryHttpClient
from codestrata.telemetry.infrastructure.http_transport import HttpTelemetryTransport
from codestrata.telemetry.transport_configuration import TelemetryTransportConfiguration


def create_http_telemetry_transport(
    configuration: TelemetryTransportConfiguration,
    *,
    client: TelemetryHttpClient | None = None,
) -> HttpTelemetryTransport:
    """Build an HTTP transport from validated configuration.

    Product opt-in resolves this via ``product_transport`` when a Community
    credential is present. ``create_default_telemetry_runtime()`` does not.
    """

    return HttpTelemetryTransport(configuration, client=client)


__all__ = ["create_http_telemetry_transport"]
