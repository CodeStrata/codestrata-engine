"""No consent prompt on product paths (Slice 9.2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.prompt import maybe_prompt_telemetry_opt_in
from codestrata.telemetry.service import reset_telemetry_singletons


def test_I_J_prompt_is_noop_interactive_and_ci(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        '{"enabled": false, "decision_made": false}',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "true")
    reset_telemetry_singletons()

    with patch("typer.confirm") as confirm:
        with patch("typer.echo") as echo:
            maybe_prompt_telemetry_opt_in()
            maybe_prompt_telemetry_opt_in(quiet=False, json_output=False)
            maybe_prompt_telemetry_opt_in(quiet=True, json_output=True)
            confirm.assert_not_called()
            echo.assert_not_called()

    assert (home / "installation_id").exists() is False
