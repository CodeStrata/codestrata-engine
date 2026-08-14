"""Side-effect-free and preference-aware status tests (Slice 9.7 / 19.4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    get_last_interactive_prompt_result,
    reset_telemetry_singletons,
)
from codestrata.telemetry.status import build_privacy_first_telemetry_status


def test_A_B_C_D_E_status_reports_persisted_preference(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "decision_made": True,
                "schema_version": "1.0.0",
                "local_counters": {"assessment_completed": 9},
            }
        ),
        encoding="utf-8",
    )
    (home / "installation_id").write_text(
        "55555555-5555-4555-8555-555555555555\n", encoding="utf-8"
    )
    (home / "queue").mkdir()
    (home / "queue" / "event.json").write_text("{}", encoding="utf-8")
    before = {
        str(p.relative_to(home)): p.read_bytes()
        for p in home.rglob("*")
        if p.is_file()
    }
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv(
        "CODESTRATA_TELEMETRY_ENDPOINT",
        "https://example.invalid/t?token=super-secret",
    )
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.service.get_legacy_telemetry_service") as legacy:
        with patch("codestrata.telemetry.transport.send_payload") as send:
            with patch("codestrata.telemetry.identity.read_installation_id") as read_id:
                with patch(
                    "codestrata.telemetry.identity.ensure_installation_id"
                ) as ensure_id:
                    runner = CliRunner()
                    result = runner.invoke(app, ["telemetry", "status"])
                    legacy.assert_not_called()
                    send.assert_not_called()
                    read_id.assert_not_called()
                    ensure_id.assert_not_called()

    assert result.exit_code == 0
    out = result.stdout
    assert "Preference: Enabled (legacy v1" in out or "Preference: Enabled (v2" in out
    assert "Default: Disabled" in out
    assert "55555555" not in out
    assert "super-secret" not in out
    assert "example.invalid" not in out
    assert "enabled by default: yes" not in out.lower()
    assert "queue_depth" not in out
    assert "endpoint_configured" not in out
    after = {
        str(p.relative_to(home)): p.read_bytes()
        for p in home.rglob("*")
        if p.is_file()
    }
    assert after == before


def test_P_Q_malformed_preference_is_treated_as_undecided(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text("{not-json", encoding="utf-8")
    (home / "installation_id").write_text("not-a-uuid\n", encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    runner = CliRunner()
    with patch(
        "codestrata.telemetry.service.TelemetryService",
        side_effect=RuntimeError("legacy boom"),
    ):
        result = runner.invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Preference: Not configured" in result.stdout
    assert "Default: Disabled" in result.stdout


def test_H_I_J_no_prompt_no_stdin_no_transmit(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt",
        side_effect=AssertionError("prompt must not run"),
    ):
        with patch("codestrata.telemetry.transport.send_payload") as send:
            result = CliRunner().invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    send.assert_not_called()
    assert "y/N" not in result.stdout
    assert "Allow privacy-safe" not in result.stdout


def test_R_S_status_does_not_consume_prompt_guard(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "status"])
    assert get_last_interactive_prompt_result() is None

    from codestrata.telemetry.persisted_consent import persist_v2_yes

    persist_v2_yes(path=home / "telemetry.json")
    reset_telemetry_singletons()
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        telemetry_allow=True,
    )
    assert telemetry.runtime.session.decision_source.value == "persisted_preference"
    prompt = get_last_interactive_prompt_result()
    assert prompt is not None
    assert getattr(prompt, "prompted") is False


def test_status_factory_does_not_accept_home() -> None:
    # Factory signature is policy-only; calling with no args is sufficient.
    a = build_privacy_first_telemetry_status()
    b = build_privacy_first_telemetry_status()
    assert a.to_stable_json() == b.to_stable_json()
