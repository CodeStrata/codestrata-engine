"""Preference reuse / legacy enable isolation for interactive consent (Slice 19.4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    get_legacy_telemetry_service,
    reset_telemetry_singletons,
)


def test_E_F_persisted_preference_skips_prompt(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "decision_made": True,
                "schema_version": "1.0.0",
                # Decline upgrade so one-time v2 prompt does not fire (Slice 20.9).
                "v2_upgrade_declined": True,
            }
        ),
        encoding="utf-8",
    )
    (home / "installation_id").write_text(
        "55555555-5555-4555-8555-555555555555\n", encoding="utf-8"
    )
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()

    calls = 0

    def reader(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        return "n"

    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=reader,
        echo_func=lambda _m: None,
    )

    assert calls == 0
    assert telemetry.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert (
        telemetry.runtime.session.decision_source
        is TelemetryDecisionSource.PERSISTED_PREFERENCE
    )
    assert {p.name: p.read_bytes() for p in home.iterdir()} == before


def test_legacy_enable_persists_preference_and_skips_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_legacy_telemetry_service(home=home).enable(emit_events=False)
    reset_telemetry_singletons()
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
        echo_func=lambda _m: None,
    )
    assert telemetry.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert (
        telemetry.runtime.session.decision_source.value == "persisted_preference"
    )
