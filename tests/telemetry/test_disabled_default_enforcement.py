"""Slice 9.2 — disabled-by-default product enforcement."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.enforcement import (
    assert_runtime_disabled_by_default,
    create_enforced_product_telemetry,
)
from codestrata.telemetry.runtime_factory import create_default_telemetry_runtime
from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_factory_disabled_no_side_effects(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    runtime = create_default_telemetry_runtime()
    assert_runtime_disabled_by_default(runtime)
    assert list(home.iterdir()) == []


def test_product_service_is_disabled_facade(monkeypatch, tmp_path: Path) -> None:
    reset_telemetry_singletons()
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path / "h"))
    (tmp_path / "h").mkdir()
    prefs = tmp_path / "h" / "telemetry.json"
    prefs.write_text('{"enabled": true, "decision_made": true}', encoding="utf-8")
    facade = get_telemetry_service()
    assert facade.is_enabled() is False
    assert facade.status()["runtime_decision"] == "disabled_by_default"
    assert facade.status()["legacy_consent_not_reused"] is True


def test_A_saved_enabled_preference_does_not_activate_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "codestrata"
    home.mkdir()
    (home / "telemetry.json").write_text(
        '{"enabled": true, "decision_made": true, "schema_version": "1.0.0"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    reset_telemetry_singletons()
    product = create_enforced_product_telemetry()
    assert product.is_enabled() is False
    assert product.runtime.session.telemetry_enabled is False
    with patch("codestrata.telemetry.transport.send_payload") as send:
        product.record_assessment_started(ai_enabled=False)
        send.assert_not_called()
