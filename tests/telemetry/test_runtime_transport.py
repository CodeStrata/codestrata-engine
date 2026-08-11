"""Transport port tests (Slice 9.1)."""

from __future__ import annotations

from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.projection import project_runtime_event
from codestrata.telemetry.transport import TelemetryTransportResultKind


def test_unavailable_transport_never_sent() -> None:
    event = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    result = UnavailableTelemetryTransport().send(event)
    assert result.kind is TelemetryTransportResultKind.UNAVAILABLE
    assert result.kind is not TelemetryTransportResultKind.SENT


def test_capture_transport_accepts_privacy_safe_only() -> None:
    capture = CaptureTelemetryTransport()
    projected = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    result = capture.send(projected)
    assert result.kind is TelemetryTransportResultKind.SENT
    assert len(capture.captured) == 1
    assert capture.captured[0].to_stable_dict() == projected.to_stable_dict()


def test_capture_rejects_non_privacy_safe() -> None:
    capture = CaptureTelemetryTransport()
    result = capture.send("raw")  # type: ignore[arg-type]
    assert result.kind is TelemetryTransportResultKind.REJECTED
    assert capture.captured == []


def test_capture_can_simulate_unavailable() -> None:
    capture = CaptureTelemetryTransport(result=TelemetryTransportResultKind.UNAVAILABLE)
    projected = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_COMPLETED)
    )
    assert capture.send(projected).kind is TelemetryTransportResultKind.UNAVAILABLE
