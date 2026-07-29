"""CLI tests for architecture report inspection (Phase 4.2.5)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli.architecture import architecture_app


def _write_report(tmp_path: Path) -> Path:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.2",
                "assessment": {
                    "architecture": {
                        "section_id": "report.architecture",
                        "section_version": "1.0.0",
                        "status": "succeeded",
                        "status_label": "Succeeded",
                        "executive_summary": "Summary text.",
                        "architecture_pack_id": "architecture.core",
                        "architecture_pack_version": "1.0.0",
                        "findings": [
                            {
                                "finding_id": "f1",
                                "title": "Cycle",
                                "severity": "medium",
                                "linked_to_conclusion": True,
                            }
                        ],
                        "conclusions": [
                            {
                                "conclusion_id": "c1",
                                "title": "Boundary",
                                "materiality": "material",
                            }
                        ],
                        "recommendation_groups": [
                            {
                                "recommendation_group_id": "r1",
                                "title": "Restore boundaries",
                            }
                        ],
                        "coverage_summary": [
                            {
                                "label": "Extraction coverage",
                                "status": "measured",
                                "display": "Complete for the analyzed source set.",
                            }
                        ],
                        "limitations": [
                            {
                                "category": "static_analysis",
                                "summary": "No runtime observation.",
                            }
                        ],
                        "traceability_summary": {
                            "summary": "2 relationships.",
                            "sample_edges": [
                                {
                                    "relation": "supports",
                                    "source_id": "c1",
                                    "target_id": "f1",
                                }
                            ],
                        },
                        "key_metrics": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_architecture_report_inspect(tmp_path: Path) -> None:
    report = _write_report(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        architecture_app,
        ["report", "inspect", "--report", str(report)],
    )
    assert result.exit_code == 0
    assert "report.architecture@1.0.0" in result.stdout
    assert "Summary text." in result.stdout


def test_architecture_report_json_and_missing(tmp_path: Path) -> None:
    report = _write_report(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        architecture_app,
        ["report", "conclusions", "--report", str(report), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["conclusions"][0]["conclusion_id"] == "c1"

    missing = runner.invoke(
        architecture_app,
        ["report", "inspect", "--report", str(tmp_path / "missing.json")],
    )
    assert missing.exit_code != 0
