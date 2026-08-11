"""SV.4 artifact enumeration tests."""

from __future__ import annotations

import json
from pathlib import Path

from verification.repository_assessment.artifacts import enumerate_artifacts


def test_enumerate_required_and_missing(tmp_path: Path) -> None:
    run = tmp_path / "reports" / "sample" / "20260101-000000"
    run.mkdir(parents=True)
    (run / "report.json").write_text(
        json.dumps({"schema_version": "1.2", "assessment": {}}),
        encoding="utf-8",
    )
    (run / "findings.json").write_text("[]", encoding="utf-8")
    (run / "recommendations.json").write_text("[]", encoding="utf-8")
    (run / "report.html").write_text("<html></html>", encoding="utf-8")
    inventory = enumerate_artifacts(tmp_path, "reports")
    assert inventory.run_directory_relative is not None
    by_name = inventory.by_name()
    assert by_name["report.json"].classification == "required"
    assert by_name["report.json"].schema_version == "1.2"
    assert "report.html" in inventory.actual_names()


def test_missing_run_directory(tmp_path: Path) -> None:
    inventory = enumerate_artifacts(tmp_path, "reports")
    assert all(r.classification == "missing" for r in inventory.records)
