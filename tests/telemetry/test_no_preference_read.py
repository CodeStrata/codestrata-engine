"""Product path must not read saved telemetry preferences."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.prompt import maybe_prompt_telemetry_opt_in
from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def _snapshot(home: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not home.exists():
        return out
    for path in sorted(home.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(home))] = path.read_text(encoding="utf-8")
    return out


def test_B_assess_path_does_not_read_preferences(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    prefs = home / "telemetry.json"
    prefs.write_text(
        json.dumps({"enabled": True, "decision_made": True, "schema_version": "1.0.0"}),
        encoding="utf-8",
    )
    before = _snapshot(home)
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.preferences.load_preferences") as load:
        maybe_prompt_telemetry_opt_in()
        telemetry = get_telemetry_service()
        telemetry.record_assessment_started(ai_enabled=True, domains=["cloud"])
        telemetry.record_assessment_completed(
            ai_enabled=True,
            ai_executed=False,
            success=True,
            duration_ms=12.0,
        )
        load.assert_not_called()

    assert _snapshot(home) == before


def test_malformed_preference_does_not_affect_product(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    facade = get_telemetry_service()
    assert facade.is_enabled() is False
    facade.record_version_check()
    assert (home / "telemetry.json").read_text(encoding="utf-8") == "{not-json"
