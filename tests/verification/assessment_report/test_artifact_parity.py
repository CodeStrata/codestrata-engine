"""SV.5 artifact parity tests."""

from __future__ import annotations

import json
from pathlib import Path

from verification.assessment_report.artifact_parity import (
    check_artifact_inventory,
    check_artifact_parity,
)
from verification.assessment_report.loaders import load_run_directory


def _run(tmp_path: Path, *, finding_id: str = "F-1") -> object:
    root = tmp_path / "run"
    root.mkdir()
    report = {
        "schema_version": "1.2",
        "assessment": {
            "findings": [{"id": finding_id, "severity": "low"}],
            "deterministic_recommendations": [{"id": "R-1", "supporting_finding_ids": [finding_id]}],
            "priority_actions": [],
            "evidence": [],
            "ai": {"executed": False, "provider_invoked": False, "status": "not_requested"},
            "technologies": [],
        },
    }
    (root / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (root / "findings.json").write_text(
        json.dumps({"finding_count": 1, "findings": [{"id": finding_id, "severity": "low"}]}),
        encoding="utf-8",
    )
    (root / "recommendations.json").write_text(
        json.dumps(
            {
                "recommendation_count": 1,
                "recommendations": [{"id": "R-1", "supporting_finding_ids": [finding_id]}],
            }
        ),
        encoding="utf-8",
    )
    (root / "report.html").write_text("<!DOCTYPE html><html></html>", encoding="utf-8")
    return load_run_directory(
        root, run_id="t", source="local_fixture", assessment_run_reference="runs/t"
    )


def test_inventory_and_parity(tmp_path: Path) -> None:
    run = _run(tmp_path)
    inv = check_artifact_inventory(run)
    assert all(c.ok for c in inv)
    parity = check_artifact_parity(run)
    assert all(c.ok for c in parity)
