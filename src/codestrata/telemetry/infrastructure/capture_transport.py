"""Test-only capture transport — never an implicit production default."""

from __future__ import annotations

from codestrata.telemetry.projection import PrivacySafeTelemetryEvent
from codestrata.telemetry.transport import (
    TelemetryTransportResult,
    TelemetryTransportResultKind,
)


class CaptureTelemetryTransport:
    """Retain privacy-safe events for deterministic test inspection only."""

    def __init__(
        self,
        *,
        result: TelemetryTransportResultKind = TelemetryTransportResultKind.SENT,
        raise_on_send: bool = False,
    ) -> None:
        self._result = result
        self._raise_on_send = raise_on_send
        self.captured: list[PrivacySafeTelemetryEvent] = []

    @property
    def transport_category(self) -> str:
        return "capture"

    def send(self, event: PrivacySafeTelemetryEvent) -> TelemetryTransportResult:
        if not isinstance(event, PrivacySafeTelemetryEvent):
            return TelemetryTransportResult(kind=TelemetryTransportResultKind.REJECTED)
        if self._raise_on_send:
            raise RuntimeError("capture_transport_simulated_failure")
        self.captured.append(event)
        return TelemetryTransportResult(kind=self._result)

    def clear(self) -> None:
        self.captured.clear()


__all__ = ["CaptureTelemetryTransport"]
