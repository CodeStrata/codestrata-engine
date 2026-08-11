"""One prompt per process and product wiring (Slice 9.4 / 19.4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    get_telemetry_service,
    reset_telemetry_singletons,
)


def test_M_one_prompt_per_process(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    calls: list[str] = []

    def reader(prompt: str) -> str:
        calls.append(prompt)
        return "n"

    first = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=reader,
        echo_func=lambda _m: None,
    )
    second = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=reader,
        echo_func=lambda _m: None,
    )
    assert first is second
    assert len(calls) == 1
    # Hooks reuse the same facade without prompting again.
    get_telemetry_service().record_assessment_started(ai_enabled=False)
    get_telemetry_service().record_report_opened()
    assert len(calls) == 1


def test_N_events_do_not_reprompt(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    calls = 0

    def reader(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        return "y"

    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=reader,
        echo_func=lambda _m: None,
    )
    for _ in range(5):
        telemetry.runtime.record(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
        )
    assert calls == 1
    assert telemetry.is_enabled() is True


def test_D_allow_persists_preference_without_network(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
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
            stdin_interactive=True,
            automation_detected=False,
            input_func=lambda _p: "yes",
            echo_func=lambda _m: None,
        )
        telemetry.record_assessment_started(ai_enabled=False)
        send.assert_not_called()
    leftover = [p for p in home.rglob("*") if p.is_file()]
    assert (home / "telemetry.json") in leftover
    # Optional anonymous installation identity may also appear once authorized.
    unexpected = [
        p for p in leftover if p.name not in {"telemetry.json", "installation_id"}
    ]
    assert unexpected == []
    assert telemetry.runtime.session.counters.transport_sent == 0
    assert telemetry.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert telemetry.runtime.session.consent.persisted is True
