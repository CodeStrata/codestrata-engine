"""Additional assessment isolation boundary tests (Slice 9.12)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.assessment_lifecycle import lifecycle_event_names
from codestrata.telemetry.service import reset_telemetry_singletons
from codestrata.telemetry.status import build_privacy_first_telemetry_status


def test_status_includes_assessment_isolation_policy() -> None:
    status = build_privacy_first_telemetry_status()
    names = {name for name, _ in status.policy_versions}
    assert "assessment_isolation" in names
    assert "assessment_isolation_primary_authoritative" in status.limitation_codes


def test_lifecycle_contract_stable() -> None:
    assert lifecycle_event_names(success=True)[0] == "feature_invoked"
    assert lifecycle_event_names(success=False)[1] == "operation_failed"


def test_non_interactive_ci_no_prompt_no_home_files(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CI", "true")
    reset_telemetry_singletons()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"n"}\n', encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt",
        side_effect=AssertionError("must not prompt"),
    ):
        result = runner.invoke(
            app,
            [
                "assess",
                "--repo",
                str(repo),
                "--output",
                str(out),
                "--no-ai",
                "--quiet",
            ],
        )
    assert result.exit_code == 0
    assert list(home.iterdir()) == []
    assert "y/N" not in (result.stdout + result.stderr)


def test_platform_boundary_assessment_isolation_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
    for name in (
        "assessment_isolation.py",
        "assessment_isolation_policy.py",
        "assessment_lifecycle.py",
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert "codestrata_platform" not in text
        assert "boto3" not in text
