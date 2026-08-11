"""Determinism of session consent outputs (Slice 9.3)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.consent import allow_session_consent, default_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime


def test_consent_and_diagnostics_deterministic(tmp_path: Path, monkeypatch) -> None:
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    home_a.mkdir()
    home_b.mkdir()
    (home_a / "telemetry.json").write_text('{"enabled": true}', encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home_a))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://a.example")
    ra = create_session_telemetry_runtime(consent=allow_session_consent())
    ra.record(RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED))
    out_a = (
        allow_session_consent().to_stable_dict(),
        ra.diagnostics().to_stable_dict()["decision"],
        ra.preview(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
        ).to_stable_json(),
    )

    monkeypatch.setenv("CODESTRATA_HOME", str(home_b))
    monkeypatch.delenv("CODESTRATA_TELEMETRY_ENDPOINT", raising=False)
    rb = create_session_telemetry_runtime(consent=allow_session_consent())
    rb.record(RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED))
    out_b = (
        allow_session_consent().to_stable_dict(),
        rb.diagnostics().to_stable_dict()["decision"],
        rb.preview(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
        ).to_stable_json(),
    )
    assert out_a[0] == out_b[0]
    assert out_a[1] == out_b[1]
    assert out_a[2] == out_b[2]
    assert default_session_consent().to_stable_dict()["decision"] == "disabled_by_default"
    assert str(home_a) not in out_a[2]
