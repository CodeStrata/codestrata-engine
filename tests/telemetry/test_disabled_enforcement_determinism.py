"""Determinism of disabled-default enforcement outputs."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.enforcement import create_enforced_product_telemetry
from codestrata.telemetry.service import reset_telemetry_singletons


def test_disabled_enforcement_determinism(tmp_path: Path, monkeypatch) -> None:
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    home_a.mkdir()
    home_b.mkdir()
    (home_a / "telemetry.json").write_text(
        '{"enabled": true, "decision_made": true}', encoding="utf-8"
    )
    (home_b / "installation_id").write_text(
        "33333333-3333-4333-8333-333333333333\n", encoding="utf-8"
    )

    monkeypatch.setenv("CODESTRATA_HOME", str(home_a))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://a.example/t")
    reset_telemetry_singletons()
    fa = create_enforced_product_telemetry()
    fa.record_assessment_started(ai_enabled=False, domains=["cloud", "security"])
    out_a = (
        fa.status()["runtime_decision"],
        fa.runtime.diagnostics().to_stable_json(),
        fa.show_sample_payload(),
    )

    monkeypatch.setenv("CODESTRATA_HOME", str(home_b))
    monkeypatch.delenv("CODESTRATA_TELEMETRY_ENDPOINT", raising=False)
    reset_telemetry_singletons()
    fb = create_enforced_product_telemetry()
    fb.record_assessment_started(ai_enabled=False, domains=["security", "cloud"])
    out_b = (
        fb.status()["runtime_decision"],
        fb.runtime.diagnostics().to_stable_json(),
        fb.show_sample_payload(),
    )

    assert out_a[0] == out_b[0] == "disabled_by_default"
    # Counters may differ only by events_seen; compare decision fields in status/preview
    assert out_a[2]["decision"] == out_b[2]["decision"]
    assert out_a[2]["transmission"] == out_b[2]["transmission"] == "none"
    assert "installation_id" not in str(out_a[2])
    assert str(home_a) not in out_a[1]
    assert str(home_b) not in out_b[1]
