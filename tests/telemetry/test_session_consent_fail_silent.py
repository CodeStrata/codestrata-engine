"""Fail-silent primary isolation with allowed consent (Slice 9.3)."""

from __future__ import annotations

from unittest.mock import patch

from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime import run_with_isolated_telemetry
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport import TelemetryTransportResultKind


def test_Z_allowed_unavailable_does_not_block_primary() -> None:
    runtime = create_session_telemetry_runtime(consent=allow_session_consent())

    def primary() -> str:
        runtime.record(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_COMPLETED)
        )
        return "ok"

    assert run_with_isolated_telemetry(primary, runtime=runtime) == "ok"
    assert runtime.session.counters.transport_unavailable == 1


def test_allowed_failing_capture_does_not_block_primary() -> None:
    capture = CaptureTelemetryTransport(raise_on_send=True)
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )

    def primary() -> int:
        result = runtime.record(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
        )
        assert result.transport_kind == TelemetryTransportResultKind.FAILED_SILENTLY.value
        return 7

    assert run_with_isolated_telemetry(primary, runtime=runtime) == 7


def test_projection_failure_under_allow_is_fail_silent() -> None:
    runtime = create_session_telemetry_runtime(consent=allow_session_consent())

    def primary() -> str:
        with patch(
            "codestrata.telemetry.runtime.project_runtime_event",
            side_effect=RuntimeError("boom"),
        ):
            runtime.record(
                RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
            )
        return "ok"

    assert run_with_isolated_telemetry(primary, runtime=runtime) == "ok"
