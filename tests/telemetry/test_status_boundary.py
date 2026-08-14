"""Status determinism, privacy, boundary, and assess isolation (Slice 9.7–9.9)."""

from __future__ import annotations

import ast
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    reset_telemetry_singletons,
)
from codestrata.telemetry.status import build_privacy_first_telemetry_status
from codestrata.telemetry.status_formatting import format_privacy_first_telemetry_status


TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_determinism_model_and_text() -> None:
    a = build_privacy_first_telemetry_status()
    b = build_privacy_first_telemetry_status()
    assert a.to_stable_json() == b.to_stable_json()
    assert format_privacy_first_telemetry_status(a) == format_privacy_first_telemetry_status(
        b
    )
    versions = [item["name"] for item in a.to_stable_dict()["policy_versions"]]
    assert versions == sorted(versions)
    assert a.to_stable_dict()["limitation_codes"] == sorted(
        a.to_stable_dict()["limitation_codes"]
    )


def test_cli_status_deterministic_output() -> None:
    runner = CliRunner()
    first = runner.invoke(app, ["telemetry", "status"])
    second = runner.invoke(app, ["telemetry", "status"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.stdout == second.stdout


def test_status_then_non_interactive_assess(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "status"])
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
    )
    assert telemetry.runtime.session.decision is TelemetryDecision.NON_INTERACTIVE_DISABLED


def test_status_then_allow(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "status"])
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        telemetry_allow=True,
    )
    # Allow alone cannot invent consent.
    assert telemetry.runtime.session.consent.transmission_authorized is False


def test_no_platform_datalake_imports() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.rglob("*.py"):
        if not path.name.startswith("status"):
            continue
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


def test_command_names_include_preview_not_send() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["telemetry", "--help"])
    assert result.exit_code == 0
    for name in ("status", "preview", "enable", "disable", "reset", "show"):
        assert name in result.stdout
    assert "│ send" not in result.stdout
    assert "  send " not in result.stdout
    assert "telemetry send" not in result.stdout.lower()
