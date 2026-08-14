"""No-persistence / no-network / transport gating for CLI flags (Slice 9.6 / 20.9)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.persisted_consent import persist_v2_yes
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    get_legacy_telemetry_service,
    reset_telemetry_singletons,
)


def test_D_E_F_G_H_allow_bridge_does_not_mutate_preference(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    pref = home / "telemetry.json"
    persist_v2_yes(path=pref)
    (home / "installation_id").write_text(
        "55555555-5555-4555-8555-555555555555\n", encoding="utf-8"
    )
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    monkeypatch.setattr(
        "codestrata.telemetry.product_transport.try_create_production_http_transport",
        lambda: None,
    )
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.transport.send_payload") as send:
        telemetry = ensure_interactive_product_telemetry(
            command="assess",
            telemetry_allow=True,
        )
        telemetry.record_assessment_started(ai_enabled=False)
        send.assert_not_called()

    assert (home / "installation_id").read_text(encoding="utf-8").startswith("55555555")
    assert (home / "telemetry.json").read_bytes() == before["telemetry.json"]
    assert not (home / "queue").exists()
    assert telemetry.runtime.session.counters.transport_sent == 0
    assert telemetry.runtime.session.counters.transport_unavailable >= 1


def test_I_deny_does_not_invoke_transport() -> None:
    capture = CaptureTelemetryTransport()
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_deny=True,
        transport=capture,
    )
    facade.runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert capture.captured == []
    assert facade.runtime.session.counters.transmission_attempts == 0


def test_allow_with_v2_unavailable_not_sent(tmp_path: Path, monkeypatch) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    monkeypatch.setattr(
        "codestrata.telemetry.product_transport.try_create_production_http_transport",
        lambda: None,
    )
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=pref,
    )
    assert result.consent.transmission_authorized is True
    recorded = facade.runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED)
    )
    assert recorded.transport_kind == "unavailable"
    assert recorded.status.value != "sent"


def test_allow_undecided_does_not_send(tmp_path: Path) -> None:
    capture = CaptureTelemetryTransport()
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=tmp_path / "missing.json",
        transport=capture,
    )
    facade.runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    assert capture.captured == []


def test_v2_capture_receives_privacy_safe_only(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    capture = CaptureTelemetryTransport()
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        preference_path=pref,
        transport=capture,
    )
    facade.runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    assert len(capture.captured) == 1
    payload = capture.captured[0].to_stable_dict()
    assert "repository_name" not in payload
    assert "path" not in payload
    assert "argv" not in payload


def test_W_legacy_enable_authorizes_via_persisted_preference(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_legacy_telemetry_service(home=home).enable(emit_events=False)
    # Enable writes consent_scope=2 (v2).
    data = json.loads((home / "telemetry.json").read_text(encoding="utf-8"))
    assert data.get("consent_scope") == 2
    reset_telemetry_singletons()
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
    )
    assert telemetry.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert telemetry.runtime.session.decision_source.value == "persisted_preference"
    assert telemetry.runtime.session.consent.persisted is True
