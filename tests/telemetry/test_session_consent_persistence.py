"""Consent persistence and prior-consent non-reuse (Slice 9.3)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)
from codestrata.telemetry.service import (
    get_legacy_telemetry_service,
    get_telemetry_service,
    reset_telemetry_singletons,
)


def _snapshot(home: Path) -> dict[str, str]:
    if not home.exists():
        return {}
    return {
        str(p.relative_to(home)): p.read_text(encoding="utf-8")
        for p in sorted(home.rglob("*"))
        if p.is_file()
    }


def test_A_B_allowed_and_denied_do_not_persist(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    before = _snapshot(home)
    create_session_telemetry_runtime(consent=allow_session_consent()).record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    from codestrata.telemetry.consent import deny_session_consent

    create_session_telemetry_runtime(consent=deny_session_consent()).record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert _snapshot(home) == before
    assert list(home.iterdir()) == []


def test_C_legacy_enabled_preference_does_not_authorize(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        json.dumps({"enabled": True, "decision_made": True, "schema_version": "1.0.0"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    runtime = create_default_telemetry_runtime()
    assert runtime.session.decision is TelemetryDecision.DISABLED_BY_DEFAULT
    assert get_telemetry_service().is_enabled() is False


def test_earlier_allowed_runtime_does_not_leak_into_default() -> None:
    capture = CaptureTelemetryTransport()
    allowed = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    allowed.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    assert len(capture.captured) == 1
    default = create_default_telemetry_runtime(transport=capture)
    default.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    assert len(capture.captured) == 1  # no additional capture
    assert default.session.decision is TelemetryDecision.DISABLED_BY_DEFAULT


def test_legacy_enable_command_path_does_not_authorize_product(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_legacy_telemetry_service(home=home).enable(emit_events=False)
    assert get_legacy_telemetry_service(home=home).is_enabled() is True
    reset_telemetry_singletons()
    assert get_telemetry_service().is_enabled() is False
    assert create_default_telemetry_runtime().session.transmission_authorized is False
