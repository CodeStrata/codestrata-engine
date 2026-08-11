"""SV.5 report.json / findings / recommendations unit checks."""

from __future__ import annotations

import json
from pathlib import Path

from verification.assessment_report.findings_json import check_findings_json
from verification.assessment_report.loaders import load_run_directory
from verification.assessment_report.recommendations_json import check_recommendations_json
from verification.assessment_report.report_json import check_report_json


def _write(tmp_path: Path) -> object:
    root = tmp_path / "run"
    root.mkdir()
    report = {
        "schema_version": "1.2",
        "report_version": "1.2",
        "manifest": {
            "contract_version": "1.0.0",
            "schema_version": "1.2",
            "report_version": "1.2",
            "html_report_version": "3.1",
            "enabled_sections": ["findings", "recommendations"],
            "generation_mode": "deterministic",
            "generated_at": "2026-01-01T00:00:00Z",
        },
        "assessment": {
            "schema_version": "1.2",
            "mode": "default",
            "generated_at": "2026-01-01T00:00:00Z",
            "findings": [],
            "deterministic_recommendations": [],
            "priority_actions": [],
            "evidence": [],
            "ai": {"executed": False, "provider_invoked": False, "status": "not_requested"},
            "technologies": [],
            "coverage": {
                "deterministic_analysis": "completed",
                "static_analysis": "disabled",
                "ai_interpretation": "not_requested",
            },
        },
    }
    (root / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (root / "findings.json").write_text(json.dumps({"finding_count": 0, "findings": []}), encoding="utf-8")
    (root / "recommendations.json").write_text(
        json.dumps({"recommendation_count": 0, "recommendations": []}), encoding="utf-8"
    )
    (root / "report.html").write_text("<!DOCTYPE html><html></html>", encoding="utf-8")
    return load_run_directory(
        root, run_id="t", source="local_fixture", assessment_run_reference="runs/t"
    )


def test_report_json_schema_checks(tmp_path: Path) -> None:
    run = _write(tmp_path)
    checks = {c.name: c for c in check_report_json(run)}
    assert checks["report:schema_version"].ok
    assert checks["report:ai_disabled"].ok


def test_findings_and_recommendations_empty_ok(tmp_path: Path) -> None:
    run = _write(tmp_path)
    assert all(c.ok for c in check_findings_json(run))
    assert all(c.ok for c in check_recommendations_json(run))
