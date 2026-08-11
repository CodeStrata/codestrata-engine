"""Privacy projection tests (Slice 9.1)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.errors import TelemetryRuntimeError, TelemetryRuntimeErrorCode
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.projection import project_from_mapping, project_runtime_event


def _base_event(**kwargs) -> RuntimeTelemetryEvent:
    payload = {"event_type": RuntimeEventType.APPLICATION_STARTED, **kwargs}
    return RuntimeTelemetryEvent(**payload)


def test_project_runtime_event_allowlist() -> None:
    projected = project_runtime_event(_base_event(ai_used=True))
    fields = projected.to_stable_dict()
    assert fields["event_type"] == "application_started"
    assert fields["client_name"] == "codestrata_cli"
    assert fields["ai_used"] is True
    assert "installation_id" not in fields
    assert list(fields.keys()) == sorted(fields.keys())


def test_reject_repository_name() -> None:
    with pytest.raises(TelemetryRuntimeError) as exc:
        project_from_mapping(
            {
                "event_type": "application_started",
                "client_name": "codestrata_cli",
                "repository_name": "acme/app",
            }
        )
    assert exc.value.code is TelemetryRuntimeErrorCode.UNSAFE_FIELD


def test_reject_repository_url() -> None:
    with pytest.raises(TelemetryRuntimeError) as exc:
        project_from_mapping(
            {
                "event_type": "application_started",
                "client_name": "codestrata_cli",
                "repository_url": "https://example.com/r.git",
            }
        )
    assert exc.value.code is TelemetryRuntimeErrorCode.UNSAFE_FIELD


def test_reject_cwd_path_argv_source_finding_exception_prompt_model_cost_credential() -> None:
    forbidden = {
        "cwd": "/Users/me",
        "path": "/tmp/x",
        "argv": ["codestrata", "assess"],
        "command_line": "codestrata assess",
        "source_code": "print(1)",
        "finding": "xss",
        "evidence": "line 1",
        "exception": "boom",
        "prompt": "hello",
        "response": "world",
        "model_id": "gpt-x",
        "cost": "1.23",
        "token": "secret",
        "credential": "x",
        "installation_id": "uuid",
        "unknown_field": "x",
    }
    for key, value in forbidden.items():
        with pytest.raises(TelemetryRuntimeError):
            project_from_mapping(
                {
                    "event_type": "application_started",
                    "client_name": "codestrata_cli",
                    key: value,
                }
            )


def test_safe_categorical_terms_not_rejected_as_fields() -> None:
    projected = project_from_mapping(
        {
            "event_type": "operation_failed",
            "client_name": "codestrata_cli",
            "failure_category": "unavailable",
        }
    )
    assert projected.to_stable_dict()["failure_category"] == "unavailable"


def test_path_shaped_cli_version_rejected() -> None:
    with pytest.raises(TelemetryRuntimeError):
        project_runtime_event(
            RuntimeTelemetryEvent(
                event_type=RuntimeEventType.APPLICATION_STARTED,
                cli_version="/tmp/evil",
            )
        )
