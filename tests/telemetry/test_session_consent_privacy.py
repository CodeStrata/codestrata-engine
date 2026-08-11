"""Consent cannot bypass privacy projection (Slice 9.3)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.errors import TelemetryRuntimeError
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.projection import project_from_mapping
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport import TelemetryTransportResultKind


def test_J_allowed_session_still_rejects_unsafe_fields() -> None:
    capture = CaptureTelemetryTransport()
    create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    for key, value in (
        ("repository_name", "acme"),
        ("path", "/tmp/x"),
        ("source_code", "print(1)"),
        ("prompt", "hi"),
        ("token", "secret"),
    ):
        with pytest.raises(TelemetryRuntimeError):
            project_from_mapping(
                {
                    "event_type": "application_started",
                    "client_name": "codestrata_cli",
                    key: value,
                }
            )
    assert capture.captured == []


def test_U_capture_rejects_raw_events() -> None:
    capture = CaptureTelemetryTransport()
    result = capture.send("raw")  # type: ignore[arg-type]
    assert result.kind is TelemetryTransportResultKind.REJECTED
    assert capture.captured == []
