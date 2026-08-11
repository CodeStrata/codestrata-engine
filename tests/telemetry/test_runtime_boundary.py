"""Runtime boundary and negative-scenario tests (Slice 9.1)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.projection import project_from_mapping
from codestrata.telemetry.runtime import TelemetryRuntime, default_runtime
from codestrata.telemetry.session import new_disabled_session
from codestrata.telemetry.transport import TelemetryTransportResultKind

ENGINE_TELEMETRY = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_A_runtime_defaults_disabled() -> None:
    runtime = default_runtime()
    assert runtime.session.telemetry_enabled is False
    assert runtime.session.decision is TelemetryDecision.DISABLED_BY_DEFAULT


def test_B_default_session_does_not_transmit() -> None:
    capture = CaptureTelemetryTransport()
    # Even if a capture transport is attached, disabled decision must drop.
    session = new_disabled_session(transport=capture)
    runtime = TelemetryRuntime(session)
    runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert capture.captured == []
    assert runtime.session.counters.transmission_attempts == 0


def test_S_unavailable_transport_never_returns_sent() -> None:
    projected = RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    from codestrata.telemetry.projection import project_runtime_event

    result = UnavailableTelemetryTransport().send(project_runtime_event(projected))
    assert result.kind is TelemetryTransportResultKind.UNAVAILABLE


def test_T_capture_not_implicit_default() -> None:
    assert isinstance(
        new_disabled_session().transport, UnavailableTelemetryTransport
    )
    assert not isinstance(new_disabled_session().transport, CaptureTelemetryTransport)


def test_U_preview_does_not_transmit() -> None:
    capture = CaptureTelemetryTransport()
    runtime = TelemetryRuntime(new_disabled_session(transport=capture))
    preview = runtime.preview(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    assert preview is not None
    assert preview.transmission == "none"
    assert capture.captured == []


def test_W_X_no_platform_or_datalake_imports() -> None:
    forbidden = (
        "codestrata_platform",
        "community_cloud_api",
        "boto3",
        "fastapi",
        "data_lake",
    )
    for path in ENGINE_TELEMETRY.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in forbidden:
                    assert needle not in name, f"{path}: forbidden import {name}"


def test_Y_cli_surface_preview_exists_flags_only_on_assess() -> None:
    """Slice 9.9 adds preview; allow/deny flags remain assess-only."""

    cli_root = Path(__file__).resolve().parents[2] / "src" / "codestrata" / "cli"
    telemetry_cmd = cli_root / "telemetry_cmd.py"
    assert '@telemetry_app.command("preview")' in telemetry_cmd.read_text(encoding="utf-8")
    for path in cli_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == "assess.py":
            assert "--telemetry-allow" in text
            assert "--telemetry-deny" in text
            continue
        # Docs/help may mention the flags; only Option registration outside assess is forbidden.
        for needle in (
            'Option("--telemetry-allow"',
            "Option('--telemetry-allow'",
            'Option("--telemetry-deny"',
            "Option('--telemetry-deny'",
        ):
            assert needle not in text, f"unexpected flag option registration in {path}"

def test_Z_preview_ordering_stable() -> None:
    event = RuntimeTelemetryEvent(
        event_type=RuntimeEventType.FEATURE_COMPLETED,
        enabled_assessment_heads=("b", "a"),
    )
    a = TelemetryRuntime().preview(event)
    b = TelemetryRuntime().preview(event)
    assert a is not None and b is not None
    assert a.to_stable_json() == b.to_stable_json()
    assert list(a.event.keys()) == sorted(a.event.keys())


def test_reject_exact_tokens_field_name() -> None:
    with pytest.raises(Exception):
        project_from_mapping(
            {
                "event_type": "application_started",
                "client_name": "codestrata_cli",
                "token_count": 12,
            }
        )
