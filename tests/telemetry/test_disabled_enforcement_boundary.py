"""Boundary negatives for disabled-default enforcement."""

from __future__ import annotations

import ast
from pathlib import Path

from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.runtime_factory import create_default_telemetry_runtime
from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons
from codestrata.telemetry.transport import TelemetryTransportResultKind


TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_S_no_fallback_to_active_legacy() -> None:
    reset_telemetry_singletons()
    assert isinstance(get_telemetry_service(), DisabledTelemetryFacade)


def test_U_default_transport_never_sent() -> None:
    runtime = create_default_telemetry_runtime()
    from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
    from codestrata.telemetry.projection import project_runtime_event

    result = runtime.session.transport.send(
        project_runtime_event(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
        )
    )
    assert result.kind is TelemetryTransportResultKind.UNAVAILABLE
    assert isinstance(runtime.session.transport, UnavailableTelemetryTransport)


def test_W_X_no_platform_datalake_imports() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in forbidden:
                    assert needle not in (name or ""), f"{path}: {name}"


def test_Z_diagnostics_ignore_legacy_state(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        '{"enabled": true, "decision_made": true}', encoding="utf-8"
    )
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid")
    reset_telemetry_singletons()
    d1 = get_telemetry_service().runtime.diagnostics().to_stable_dict()
    reset_telemetry_singletons()
    monkeypatch.delenv("CODESTRATA_TELEMETRY", raising=False)
    monkeypatch.delenv("CODESTRATA_TELEMETRY_ENDPOINT", raising=False)
    (home / "telemetry.json").unlink()
    d2 = get_telemetry_service().runtime.diagnostics().to_stable_dict()
    assert d1["decision"] == d2["decision"] == TelemetryDecision.DISABLED_BY_DEFAULT.value
    assert d1["telemetry_enabled"] is False
    assert d2["telemetry_enabled"] is False
    assert d1["transport_category"] == d2["transport_category"] == "unavailable"
