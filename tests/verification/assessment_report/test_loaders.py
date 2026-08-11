"""SV.5 loader tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verification.assessment_report.loaders import load_run_directory


def _write_minimal_run(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "report.json").write_text(
        json.dumps(
            {
                "schema_version": "1.2",
                "report_version": "1.2",
                "assessment": {
                    "schema_version": "1.2",
                    "findings": [],
                    "deterministic_recommendations": [],
                    "priority_actions": [],
                    "evidence": [],
                    "ai": {"executed": False, "provider_invoked": False, "status": "not_requested"},
                    "technologies": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "findings.json").write_text(
        json.dumps({"finding_count": 0, "findings": []}), encoding="utf-8"
    )
    (root / "recommendations.json").write_text(
        json.dumps({"recommendation_count": 0, "recommendations": []}), encoding="utf-8"
    )
    (root / "report.html").write_text(
        "<!DOCTYPE html><html><head></head><body><h1>x</h1></body></html>",
        encoding="utf-8",
    )
    return root


def test_load_run_directory(tmp_path: Path) -> None:
    run = _write_minimal_run(tmp_path / "run")
    loaded = load_run_directory(
        run,
        run_id="t",
        source="local_fixture",
        assessment_run_reference="runs/t",
    )
    assert loaded.report["schema_version"] == "1.2"
    assert "report.html" in loaded.present_files


def test_load_missing_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(FileNotFoundError):
        load_run_directory(
            root,
            run_id="x",
            source="local_fixture",
            assessment_run_reference="runs/x",
        )
