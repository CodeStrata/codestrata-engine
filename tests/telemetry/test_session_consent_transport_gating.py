"""Transport gating by session consent (Slice 9.3)."""

from __future__ import annotations

from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime import TelemetryRecordStatus
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)
from codestrata.telemetry.transport import TelemetryTransportResultKind


def _event() -> RuntimeTelemetryEvent:
    return RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)


def test_G_default_does_not_invoke_transport() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_default_telemetry_runtime(transport=capture)
    result = runtime.record(_event())
    assert result.status is TelemetryRecordStatus.DROPPED_DISABLED
    assert capture.captured == []
    assert runtime.session.counters.transmission_attempts == 0


def test_H_denied_does_not_invoke_transport() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=deny_session_consent(),
        transport=capture,
    )
    result = runtime.record(_event())
    assert result.status is TelemetryRecordStatus.DROPPED_DENIED
    assert capture.captured == []
    assert runtime.session.counters.transmission_attempts == 0


def test_I_allowed_unavailable_returns_unavailable_not_sent() -> None:
    runtime = create_session_telemetry_runtime(consent=allow_session_consent())
    result = runtime.record(_event())
    assert result.status is TelemetryRecordStatus.TRANSPORT_RESULT
    assert result.transport_kind == TelemetryTransportResultKind.UNAVAILABLE.value
    assert result.transport_kind != TelemetryTransportResultKind.SENT.value
    assert runtime.session.counters.transport_unavailable == 1
    assert runtime.session.counters.transport_sent == 0


def test_allowed_with_capture_receives_privacy_safe_only() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    result = runtime.record(_event())
    assert result.status is TelemetryRecordStatus.TRANSPORT_RESULT
    assert result.transport_kind == TelemetryTransportResultKind.SENT.value
    assert len(capture.captured) == 1
    fields = capture.captured[0].to_stable_dict()
    assert "installation_id" not in fields
    assert "repository" not in fields
    assert fields["event_type"] == "feature_invoked"
