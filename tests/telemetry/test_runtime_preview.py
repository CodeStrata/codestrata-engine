"""Preview contract tests (Slice 9.1)."""

from __future__ import annotations

from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.preview import preview_runtime_event
from codestrata.telemetry.runtime import TelemetryRuntime
from codestrata.telemetry.session import new_disabled_session


def test_preview_works_while_disabled_no_transmission() -> None:
    event = RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_COMPLETED)
    preview = preview_runtime_event(event, session=new_disabled_session())
    assert preview.telemetry_enabled is False
    assert preview.transmission == "none"
    assert preview.decision == "disabled_by_default"
    assert "installation_id" not in preview.event
    assert "endpoint" not in preview.to_stable_json()
    assert preview.event["event_type"] == "feature_completed"


def test_preview_omits_optional_fields_honestly() -> None:
    preview = preview_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert "cli_version" in preview.omitted_optional_fields
    assert "cli_version" not in preview.event


def test_preview_does_not_expose_raw_input() -> None:
    runtime = TelemetryRuntime()
    preview = runtime.preview(
        RuntimeTelemetryEvent(
            event_type=RuntimeEventType.APPLICATION_STARTED,
            ai_used=False,
        )
    )
    assert preview is not None
    blob = preview.to_stable_json()
    assert "to_intake_dict" not in blob
    assert "raw" not in blob
