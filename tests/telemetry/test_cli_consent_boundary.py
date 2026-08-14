"""CLI consent privacy, determinism, and boundary (Slice 9.6)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.cli_consent import select_cli_telemetry_consent
from codestrata.telemetry.cli_consent_policy import TELEMETRY_FLAG_CONFLICT_MESSAGE
from codestrata.telemetry.errors import TelemetryRuntimeError
from codestrata.telemetry.projection import project_from_mapping
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)
from codestrata.telemetry.service import reset_telemetry_singletons


TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_L_allow_cannot_bypass_privacy(tmp_path: Path) -> None:
    from codestrata.telemetry.persisted_consent import persist_v2_yes

    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    with pytest.raises(TelemetryRuntimeError):
        project_from_mapping(
            {
                "event_type": "application_started",
                "client_name": "codestrata_cli",
                "repository_name": "acme",
            }
        )
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=pref,
    )
    assert facade.runtime.session.consent.transmission_authorized is True


def test_allow_undecided_does_not_authorize(tmp_path: Path) -> None:
    facade, _ = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=tmp_path / "telemetry.json",
    )
    assert facade.runtime.session.consent.transmission_authorized is False


def test_determinism() -> None:
    a = select_cli_telemetry_consent(allow=True).to_stable_json()
    b = select_cli_telemetry_consent(allow=True).to_stable_json()
    assert a == b
    c = select_cli_telemetry_consent(deny=True).to_stable_dict()
    d = select_cli_telemetry_consent(deny=True).to_stable_dict()
    assert c == d
    assert a != select_cli_telemetry_consent(deny=True).to_stable_json()


def test_help_lists_flags_not_on_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    runner = CliRunner()
    assess_help = runner.invoke(app, ["assess", "--help"])
    assert assess_help.exit_code == 0
    help_text = (assess_help.stdout + assess_help.stderr).lower()
    assert "--telemetry-allow" in help_text
    assert "--telemetry-deny" in help_text
    assert "not saved" in help_text or "session bridge" in help_text

    scan_help = runner.invoke(app, ["scan", "--help"])
    assert scan_help.exit_code == 0
    assert "--telemetry-allow" not in scan_help.stdout
    assert "--telemetry-deny" not in scan_help.stdout

    telemetry_help = runner.invoke(app, ["telemetry", "--help"])
    assert "--telemetry-allow" not in telemetry_help.stdout


def test_A_conflict_cli_exits_before_assessment(tmp_path: Path) -> None:
    reset_telemetry_singletons()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    out = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "assess",
            "--repo",
            str(repo),
            "--output",
            str(out),
            "--no-ai",
            "--telemetry-allow",
            "--telemetry-deny",
        ],
    )
    assert result.exit_code == 2
    assert TELEMETRY_FLAG_CONFLICT_MESSAGE in (result.stdout + result.stderr)
    assert not out.exists() or not any(out.rglob("assessment.json"))
    assert not out.exists() or not any(out.rglob("report.json"))


def test_no_platform_datalake_imports() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                for needle in forbidden:
                    assert needle not in (name or ""), f"{path}: {name}"
