"""SV.3 reporting privacy tests."""

from __future__ import annotations

from pathlib import Path

from verification.cli_initialization.models import ScenarioResult, VerificationReport
from verification.cli_initialization.reporting import (
    classify_output,
    report_contains_forbidden_leak,
    sanitize_text,
)


def test_sanitize_and_classify() -> None:
    text = sanitize_text("Wrote /Users/someone/proj/codestrata.toml", workspace=Path("/tmp/ws"))
    assert "/Users/" not in text
    classes = classify_output(
        "Success: Configuration ready.\n",
        "",
        exit_code=0,
    )
    assert classes["init"] == "success"
    assert classes["safety"] == "no_traceback"


def test_report_json_has_no_leaks(tmp_path: Path) -> None:
    report = VerificationReport(
        ok=True,
        verdict="pass",
        platform="darwin",
        python_version="3.12.0",
        cli_version="0.1.0",
        scenarios=(
            ScenarioResult(
                scenario_id="A_minimal_supported_repository",
                ok=True,
                detail="ok",
                actual_artifacts=("codestrata.toml",),
                artifact_digests={"codestrata.toml": "abc"},
            ),
        ),
    )
    path = report.write_json(tmp_path / "cli-initialization-verification.json")
    payload = report.to_dict()
    assert list(payload.keys()) == sorted(payload.keys())
    assert report_contains_forbidden_leak(payload) == []
    assert "/Users/" not in path.read_text(encoding="utf-8")
