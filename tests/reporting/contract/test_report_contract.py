"""Report contract and validation tests (Phase 5.12)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codestrata.application.report_validation import (
    ReportValidationService,
    validate_report_json,
)
from codestrata.cli import app
from codestrata.models import (
    AnalysisResult,
    Effort,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Priority,
    Recommendation,
    RecommendationCategory,
    Repository,
    RepositoryFacts,
    Risk,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)
from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.contract import (
    reports_structurally_equal,
    strip_volatile_fields,
)
from codestrata.reporting.html_v2.builder import build_html_report_view_model
from codestrata.reporting.html_v2.renderer import HtmlReportRenderer
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

runner = CliRunner()
GOLDENS = Path(__file__).parent / "goldens"


def _analysis(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py", "README.md"],
            total_files=2,
        ),
        technologies=[
            Technology(
                name="FastAPI",
                category=TechnologyCategory.FRAMEWORK,
                confidence=1.0,
                source="test",
            ),
            Technology(
                name="Python",
                category=TechnologyCategory.LANGUAGE,
                version="3.12",
                confidence=1.0,
                source="test",
            ),
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=2,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[
            Finding(
                rule_id="TEST002",
                title="B finding",
                description="Second",
                category=FindingCategory.TESTING,
                severity=Severity.MEDIUM,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="tests/test_a.py", description="a")],
            ),
            Finding(
                rule_id="TEST001",
                title="A finding",
                description="First",
                category=FindingCategory.SECURITY,
                severity=Severity.HIGH,
                source=FindingSource.DETERMINISTIC,
                evidence=[
                    Evidence(file_path="src/App.py", line_number=2, description="x"),
                    Evidence(file_path="src/App.py", line_number=2, description="x"),
                ],
            ),
        ],
        recommendations=[
            Recommendation(
                rule_id="REC002",
                title="Later rec",
                description="d",
                rationale="r",
                priority=Priority.LOW,
                category=RecommendationCategory.TESTING,
                effort=Effort.SMALL,
                risk=Risk.LOW,
                related_finding_ids=[],
                actions=["a"],
            ),
            Recommendation(
                rule_id="REC001",
                title="Urgent rec",
                description="d",
                rationale="r",
                priority=Priority.HIGH,
                category=RecommendationCategory.SECURITY,
                effort=Effort.MEDIUM,
                risk=Risk.HIGH,
                related_finding_ids=[],
                actions=["a", "b"],
            ),
        ],
    )


def _report_input(tmp_path: Path, *, generated_at: datetime) -> ModernizationReportInput:
    return ModernizationReportInput(
        analysis_result=_analysis(tmp_path),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=generated_at,
        knowledge_repository_id="repo-sample",
        knowledge_run_id="run-sample",
    )


def test_stable_ordering_and_dedupe(tmp_path: Path) -> None:
    document = build_assessment_json_document(
        _report_input(tmp_path, generated_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    )
    findings = document["assessment"]["findings"]
    assert findings[0]["severity"] == "high"
    assert findings[0]["rule_id"] == "TEST001"
    assert len(findings[0]["evidence"]) == 1
    recs = document["assessment"]["deterministic_recommendations"]
    assert recs[0]["priority"] == "high"
    assert recs[0]["title"] == "Urgent rec"
    techs = document["assessment"]["technologies"]
    assert techs[0]["category"] == "framework" or techs[0]["name"] == "FastAPI"
    assert techs[0]["name"] == "FastAPI"
    assert techs[1]["name"] == "Python"


def test_manifest_present_and_schema_compatible(tmp_path: Path) -> None:
    document = build_assessment_json_document(
        _report_input(tmp_path, generated_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    )
    assert document["schema_version"] == ASSESSMENT_JSON_SCHEMA_VERSION
    assert document["schema_version"] == "1.2"
    manifest = document["manifest"]
    assert manifest["repository_id"] == "repo-sample"
    assert manifest["scan_id"] == "run-sample"
    assert "findings" in manifest["enabled_sections"]
    assert "volatile_fields" in manifest
    assert "roadmap" not in document["assessment"]


def test_repeated_runs_structurally_equal(tmp_path: Path) -> None:
    first = build_assessment_json_document(
        _report_input(tmp_path, generated_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    )
    second = build_assessment_json_document(
        _report_input(tmp_path, generated_at=datetime(2026, 7, 26, 18, 30, tzinfo=UTC))
    )
    assert first["assessment"]["generated_at"] != second["assessment"]["generated_at"]
    assert reports_structurally_equal(first, second)
    assert strip_volatile_fields(first) == strip_volatile_fields(second)


def test_golden_json_and_html(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path, generated_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    document = build_assessment_json_document(report_input)
    canonical = strip_volatile_fields(document)
    # Drop manifest.generated_at already via volatile; also normalize codestrata version.
    canonical["manifest"]["codestrata_version"] = "TEST"
    golden_json = GOLDENS / "sample_report.canonical.json"
    if not golden_json.exists():
        GOLDENS.mkdir(parents=True, exist_ok=True)
        golden_json.write_text(
            json.dumps(canonical, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    expected = json.loads(golden_json.read_text(encoding="utf-8"))
    expected["manifest"]["codestrata_version"] = "TEST"
    assert canonical == expected

    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert 'id="executive-summary"' in html
    assert "Executive Summary" in html
    assert "Should I care?" in html
    assert "Leadership Verdict" in html
    golden_html = GOLDENS / "sample_report.fragments.txt"
    fragments = [
        'id="executive-summary"',
        'id="leadership-verdict"',
        'id="findings"',
        'id="priority-actions"',
        "Urgent rec",
        "A finding",
    ]
    if not golden_html.exists():
        golden_html.write_text("\n".join(fragments) + "\n", encoding="utf-8")
    for line in golden_html.read_text(encoding="utf-8").splitlines():
        if line.strip():
            assert line.strip() in html


def test_validation_service_and_cli(tmp_path: Path) -> None:
    document = build_assessment_json_document(
        _report_input(tmp_path, generated_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    )
    path = tmp_path / "report.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    result = validate_report_json(path)
    assert result.ok
    assert result.schema_version == "1.2"

    broken = dict(document)
    broken["assessment"] = dict(document["assessment"])
    broken["assessment"]["findings"] = list(document["assessment"]["findings"]) + [
        dict(document["assessment"]["findings"][0])
    ]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(broken), encoding="utf-8")
    failed = ReportValidationService().validate_path(bad)
    assert not failed.ok
    assert any(item.code == "duplicate_finding_id" for item in failed.issues)

    cli = runner.invoke(app, ["report", "validate", str(path)])
    assert cli.exit_code == 0, cli.stdout + cli.stderr
    assert "PASS" in cli.stdout


def test_enum_normalization(tmp_path: Path) -> None:
    document = build_assessment_json_document(
        _report_input(tmp_path, generated_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    )
    rec = document["assessment"]["deterministic_recommendations"][0]
    assert rec["effort"] in {"s", "m", "l", "xl", "xs", "unknown"}
    assert rec["risk"] in {"high", "medium", "low"}
