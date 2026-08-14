"""CLI, status, assess-isolation, and boundary tests for telemetry preview."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.preview_builder import build_privacy_first_telemetry_preview
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    reset_telemetry_singletons,
)


TELEMETRY_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "codestrata" / "telemetry"
)


def test_cli_preview_default_json() -> None:
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "preview"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_name"] == "privacy-first-telemetry-preview"
    assert payload["event_name"] == "feature_invoked"
    assert payload["transmission_performed"] is False
    assert payload["transport_status"] == "unavailable"
    assert payload["event"]["event_type"] == "feature_invoked"
    assert result.stderr == ""


def test_cli_preview_event_selector() -> None:
    result = CliRunner().invoke(
        app, ["telemetry", "preview", "--event", "operation_failed"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["event_name"] == "operation_failed"
    assert payload["event"]["failure_category"] == "unavailable"


def test_cli_preview_invalid_event() -> None:
    result = CliRunner().invoke(app, ["telemetry", "preview", "--event", "not_real"])
    assert result.exit_code == 2
    assert "Invalid preview" in (result.stderr or result.stdout)
    assert "schema_name" not in result.stdout


def test_cli_preview_help() -> None:
    result = CliRunner().invoke(app, ["telemetry", "preview", "--help"])
    assert result.exit_code == 0
    text = (result.stdout + result.stderr).lower()
    assert "does not transmit" in text or "local only" in text or "illustrative" in text
    assert "privacy-safe" in text or "event" in text


def test_status_reports_preview_available(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    result = CliRunner().invoke(app, ["telemetry", "status"])
    assert result.exit_code == 0
    assert "Anonymous Community telemetry" in result.stdout
    assert "Preference: Not configured" in result.stdout
    assert "Change later: `codestrata telemetry enable|disable`" in result.stdout


def test_preview_does_not_use_legacy(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    with patch(
        "codestrata.cli.telemetry_cmd.get_legacy_telemetry_service",
        side_effect=AssertionError("legacy must not run for preview"),
    ):
        result = CliRunner().invoke(app, ["telemetry", "preview"])
    assert result.exit_code == 0
    assert list(home.iterdir()) == []


def test_preview_then_interactive_assess_still_eligible(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "preview"])
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=lambda _p: "n",
        echo_func=lambda _m: None,
    )
    assert telemetry.runtime.session.decision is TelemetryDecision.DENIED_FOR_SESSION


def test_preview_then_allow_flag(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "preview"])
    # Allow alone does not invent consent (Slice 20.9).
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        telemetry_allow=True,
    )
    assert telemetry.runtime.session.consent.transmission_authorized is False


def test_preview_then_non_interactive(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    CliRunner().invoke(app, ["telemetry", "preview"])
    telemetry = ensure_interactive_product_telemetry(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
    )
    assert telemetry.runtime.session.decision is TelemetryDecision.NON_INTERACTIVE_DISABLED


def test_legacy_show_remains() -> None:
    result = CliRunner().invoke(app, ["telemetry", "show", "--help"])
    assert result.exit_code == 0
    assert "legacy" in (result.stdout + result.stderr).lower() or "sample" in (
        result.stdout + result.stderr
    ).lower()


def test_no_platform_imports_in_preview_modules() -> None:
    forbidden = ("codestrata_platform", "codestrata_platform.community_cloud","community_cloud_api", "boto3", "fastapi", "data_lake")
    for path in TELEMETRY_ROOT.glob("preview*.py"):
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


def test_builder_matches_cli_default() -> None:
    built = build_privacy_first_telemetry_preview()
    result = CliRunner().invoke(app, ["telemetry", "preview"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == built.to_stable_dict()
