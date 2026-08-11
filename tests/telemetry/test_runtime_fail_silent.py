"""Fail-silent runtime tests (Slice 9.1 / 9.3)."""

from __future__ import annotations

from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime import (
    TelemetryRecordStatus,
    TelemetryRuntime,
    record_telemetry_safely,
)
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport import TelemetryTransportResultKind


def test_record_drops_when_disabled() -> None:
    runtime = TelemetryRuntime()
    result = record_telemetry_safely(
        runtime,
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED),
    )
    assert result.status is TelemetryRecordStatus.DROPPED_DISABLED
    assert result.transport_kind == TelemetryTransportResultKind.DISABLED.value
    assert runtime.session.counters.events_dropped == 1
    assert runtime.session.counters.transmission_attempts == 0


def test_transport_exception_fails_silently() -> None:
    capture = CaptureTelemetryTransport(raise_on_send=True)
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    result = record_telemetry_safely(
        runtime,
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED),
    )
    assert result.status is TelemetryRecordStatus.TRANSPORT_RESULT
    assert result.transport_kind == TelemetryTransportResultKind.FAILED_SILENTLY.value
    assert runtime.session.counters.failures >= 1


def test_invalid_event_fails_silently_no_raise() -> None:
    class _Broken:
        def to_intake_dict(self):
            raise RuntimeError("boom")

    runtime = TelemetryRuntime()
    result = record_telemetry_safely(runtime, _Broken())  # type: ignore[arg-type]
    assert result.status is TelemetryRecordStatus.FAILED_SILENTLY
    assert result.error_code is not None
