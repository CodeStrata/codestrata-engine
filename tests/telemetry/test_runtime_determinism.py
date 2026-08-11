"""Determinism tests for runtime projection and preview (Slice 9.1)."""

from __future__ import annotations

import os

from codestrata.telemetry.events import (
    OsFamily,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.preview import preview_runtime_event
from codestrata.telemetry.projection import project_runtime_event
from codestrata.telemetry.runtime import TelemetryRuntime
from codestrata.telemetry.session import new_disabled_session


def _event(heads: tuple[str, ...]) -> RuntimeTelemetryEvent:
    return RuntimeTelemetryEvent(
        event_type=RuntimeEventType.FEATURE_INVOKED,
        enabled_assessment_heads=heads,
        os_family=OsFamily.MACOS,
        ai_used=False,
        offline_mode=True,
    )


def test_reversed_heads_and_dict_order_identical() -> None:
    a = project_runtime_event(_event(("security", "cloud", "testing")))
    b = project_runtime_event(_event(("testing", "cloud", "security")))
    assert a.to_stable_dict() == b.to_stable_dict()
    assert a.to_stable_json() == b.to_stable_json()
    pa = preview_runtime_event(_event(("security", "cloud")))
    pb = preview_runtime_event(_event(("cloud", "security")))
    assert pa.to_stable_json() == pb.to_stable_json()


def test_determinism_ignores_cwd_and_env(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path / "home-a"))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    first = preview_runtime_event(
        _event(("cloud",)),
        session=new_disabled_session(),
    ).to_stable_json()

    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path / "home-b"))
    monkeypatch.delenv("CODESTRATA_TELEMETRY", raising=False)
    second = preview_runtime_event(
        _event(("cloud",)),
        session=new_disabled_session(),
    ).to_stable_json()
    assert first == second


def test_diagnostics_deterministic() -> None:
    runtime = TelemetryRuntime()
    runtime.record(_event(("testing", "security")))
    d1 = runtime.diagnostics().to_stable_json()
    d2 = runtime.diagnostics().to_stable_json()
    assert d1 == d2
    assert "PYTHONHASHSEED" not in d1
    _ = os.environ.get("PYTHONHASHSEED")
