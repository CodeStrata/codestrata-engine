"""Assessment-path telemetry enforcement."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.prompt import maybe_prompt_telemetry_opt_in
from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_assessment_hooks_disabled_no_fs_mutation(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        '{"enabled": true, "decision_made": true}',
        encoding="utf-8",
    )
    (home / "installation_id").write_text(
        "22222222-2222-4222-8222-222222222222\n", encoding="utf-8"
    )
    queue = home / "telemetry-queue.jsonl"
    queue.write_text("{}\n", encoding="utf-8")
    before_files = {
        p.name: p.read_bytes() for p in home.iterdir() if p.is_file()
    }
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.transport.send_payload") as send:
        maybe_prompt_telemetry_opt_in(quiet=False, json_output=False)
        telemetry = get_telemetry_service()
        telemetry.record_assessment_started(ai_enabled=False, domains=["security"])
        telemetry.record_assessment_completed(
            ai_enabled=False,
            ai_executed=False,
            success=True,
            duration_ms=100.0,
            domains=["security"],
            repo_root=tmp_path / "repo",
        )
        send.assert_not_called()

    after_files = {p.name: p.read_bytes() for p in home.iterdir() if p.is_file()}
    assert after_files == before_files


def test_M_unwritable_home_does_not_break_assessment_hooks(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "ro-home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    # Product facade never writes — even if home later becomes unwritable.
    home.chmod(0o500)
    try:
        telemetry = get_telemetry_service()
        telemetry.record_assessment_started(ai_enabled=True)
        assert telemetry.is_enabled() is False
    finally:
        home.chmod(0o700)
