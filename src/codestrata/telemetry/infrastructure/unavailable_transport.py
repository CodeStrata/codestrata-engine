"""Default unavailable/no-op telemetry transport (Slice 9.1)."""

from __future__ import annotations

from codestrata.telemetry.projection import PrivacySafeTelemetryEvent
from codestrata.telemetry.transport import (
    TelemetryTransportResult,
    TelemetryTransportResultKind,
)


class UnavailableTelemetryTransport:
    """Production-safe default: no network, no filesystem, no false sent."""

    @property
    def transport_category(self) -> str:
        return "unavailable"

    def send(self, event: PrivacySafeTelemetryEvent) -> TelemetryTransportResult:
        _ = event
        return TelemetryTransportResult(kind=TelemetryTransportResultKind.UNAVAILABLE)


def default_unavailable_transport() -> UnavailableTelemetryTransport:
    return UnavailableTelemetryTransport()


__all__ = [
    "UnavailableTelemetryTransport",
    "default_unavailable_transport",
]
