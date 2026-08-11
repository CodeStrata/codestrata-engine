"""Preview under session consent (Slice 9.3)."""

from __future__ import annotations

from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime


def test_S_preview_never_transmits_even_when_allowed() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    preview = runtime.preview(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_COMPLETED)
    )
    assert preview is not None
    assert preview.transmission == "none"
    assert preview.transmission_performed is False
    assert preview.transmission_authorized is True
    assert capture.captured == []
    blob = preview.to_stable_json()
    assert "installation_id" not in blob
    assert "endpoint" not in blob
    assert "telemetry.json" not in blob


def test_T_preview_excludes_saved_preference_fields() -> None:
    runtime = create_session_telemetry_runtime(consent=deny_session_consent())
    preview = runtime.preview(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert preview is not None
    assert preview.decision == "denied_for_session"
    assert "preference" not in preview.to_stable_json()
