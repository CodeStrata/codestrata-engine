"""G40-D002: assess/compare HTML is the projector output for the same object."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.assessment.canonical_records import (
    CANONICAL_COVERAGE_KEY,
    CANONICAL_FRESHNESS_KEY,
    CANONICAL_HOTSPOTS_KEY,
    CANONICAL_OWNERSHIP_KEY,
)
from codestrata.domain.contracts.enums import (
    ContributorRole,
    HotspotListKind,
    OwnershipScope,
    ResultStatus,
)
from codestrata.domain.contracts.hotspot import (
    ChangeSummary,
    ContributorRecord,
    EngineeringHotspot,
    OwnershipConcentration,
    build_priority_explanation,
)
from codestrata.domain.findings import (
    Finding as RuleFinding,
)
from codestrata.domain.findings import (
    FindingCategory as RuleFindingCategory,
)
from codestrata.domain.findings import (
    FindingEvidence as RuleFindingEvidence,
)
from codestrata.domain.findings import (
    FindingSeverity as RuleFindingSeverity,
)
from codestrata.domain.findings import (
    RuleEvaluationResult,
)
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.enums import FindingCategory, FindingSource, Severity
from codestrata.models.evidence import Evidence
from codestrata.models.finding import Finding
from codestrata.models.repository import Repository
from codestrata.models.scan_comparison import MetricDelta, ScanComparison
from codestrata.reporters.report_paths import create_report_paths
from codestrata.reporting import AssessmentMode
from codestrata.reporting.assessment_canonical import (
    canonical_html_for_analysis,
    canonical_html_for_report,
    canonical_report_from_analysis,
    embed_canonical_views,
)
from codestrata.reporting.canonical_views import project_canonical_html
from codestrata.reporting.modernization_models import ModernizationReportInput
from codestrata.reporting.modernization_serialization import (
    write_modernization_assessment_reports,
)

_VIEW_IDS = (
    "engineering-hotspots",
    "ownership-concentration",
    "temporal-co-change",
    "change-summary",
    "capability-coverage",
    "before-after-delta",
)


def _result() -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(name="sample-repo", path=Path("sample-repo"), files=["src/App.java"]),
    )


def test_canonical_html_matches_the_same_run_object() -> None:
    result = _result()
    report = canonical_report_from_analysis(result)
    html = canonical_html_for_analysis(result)
    assert html == project_canonical_html(report)
    for view_id in _VIEW_IDS:
        assert f'id="{view_id}"' in html
    assert "no baseline" in html
    assert "Stable" not in html
    assert "health_score: none" in html
    assert report.envelope.body.hotspots == ()
    assert report.envelope.body.findings == ()
    assert "m22_records_not_attached" in html
    assert "no findings" in html
    ownership = report.envelope.body.ownership[0]
    assert ownership.status is ResultStatus.UNKNOWN
    assert ownership.serialized_ratio is None
    assert "Ownership mapping was not attached" in html


def test_assessment_writer_embeds_the_same_canonical_html(tmp_path: Path) -> None:
    result = _result()
    report_input = ModernizationReportInput(
        analysis_result=result,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 9, 27, tzinfo=UTC),
    )
    paths = create_report_paths(
        result,
        tmp_path / "out",
        timestamp="20260927-120000",
        create_directory=False,
    )
    write_modernization_assessment_reports(report_input, paths)
    html = paths.html_report_path.read_text(encoding="utf-8")
    canonical_path = paths.html_report_path.with_name("canonical-report.html")
    canonical = canonical_path.read_text(encoding="utf-8")
    baseline_view_ids = (
        "engineering-hotspots",
        "ownership-concentration",
        "temporal-co-change",
    )
    comparison_only_ids = (
        "change-summary",
        "capability-coverage",
        "before-after-delta",
    )
    for view_id in baseline_view_ids:
        assert f'id="{view_id}"' in html
        assert f'id="{view_id}"' in canonical
    for view_id in comparison_only_ids:
        assert f'id="{view_id}"' not in html
        assert f'id="{view_id}"' in canonical


def test_same_run_projects_findings_hotspots_and_comparison() -> None:
    finding = Finding(
        rule_id="quality.complexity",
        title="App is complex",
        description="cyclomatic complexity",
        category=FindingCategory.MAINTAINABILITY,
        severity=Severity.HIGH,
        source=FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path="src/App.java", line_number=4)],
    )
    result = AnalysisResult(
        repository=Repository(name="sample-repo", path=Path("sample-repo"), files=["src/App.java"]),
        findings=[finding],
    )
    projected = canonical_report_from_analysis(result)
    recorded = projected.envelope.body.findings[0]
    evidence_ids = recorded.evidence_ids
    explanation = build_priority_explanation(
        formula_version="M22.v1",
        complexity="8",
        changed_lines="3",
        ranking_value="24",
        subject_id="component:app",
        history_window="90d",
    )
    hotspot = EngineeringHotspot(
        record_id="hotspot:component:app",
        subject_id="component:app",
        input_state_digest=projected.envelope.body.working_state_digest,
        list_kind=HotspotListKind.COMPLETE_COMPARABLE,
        ranking_value="24",
        history_profile_id="history-90d",
        history_window="90d",
        contributors=(
            ContributorRecord(
                name="complexity",
                measurement_id="M16",
                measurement_version="v1",
                role=ContributorRole.RANKING,
                value="8",
                evidence_ids=evidence_ids,
            ),
            ContributorRecord(
                name="churn",
                measurement_id="M24",
                measurement_version="v1",
                role=ContributorRole.RANKING,
                value="3",
                evidence_ids=evidence_ids,
            ),
        ),
        active_finding_ids=(recorded.finding_id,),
        evidence_ids=evidence_ids,
        priority_explanation=explanation,
    )
    ownership = OwnershipConcentration(
        record_id="m25:component:app",
        scope=OwnershipScope.COMPONENT,
        subject_id="component:app",
        numerator=2,
        denominator=5,
        serialized_ratio="0.400000",
        history_profile_id="history-90d",
        evidence_ids=evidence_ids,
        status=ResultStatus.PASS,
        notes="pinned history window",
    )
    summary = ChangeSummary(
        changed_file_ids=("src/App.java",),
        changed_component_ids=("component:app",),
        changed_file_count=1,
        changed_component_count=1,
        unmapped_changed_file_count=0,
        mapping_coverage="1.000000",
        mapping_coverage_status=ResultStatus.PASS,
        boundary_spread_status=ResultStatus.UNKNOWN,
        crossed_boundary_status=ResultStatus.UNKNOWN,
        affected_test_count=None,
        graph_side="candidate",
    )
    compared = result.model_copy(
        update={
            "metadata": {
                "canonical_hotspots": [hotspot],
                "canonical_ownership": [ownership],
                "canonical_cochange": [
                    {
                        "scope": "file",
                        "left": "src/App.java",
                        "right": "src/Util.java",
                        "support": 3,
                        "union": 5,
                        "jaccard": "0.600000",
                        "supported_relation": True,
                        "qualified_incomplete_window": False,
                    }
                ],
            },
            "comparison": ScanComparison(
                baseline_available=True,
                baseline_timestamp="2026-09-01",
                current_timestamp="2026-09-27",
                compatibility_status="incompatible",
                compatibility_reasons=["ruleset_changed"],
                summary={"overall_movement": "stable"},
                metric_deltas=[
                    MetricDelta(
                        metric_name="M13.known_vulnerability",
                        unit="count",
                        base_value=1,
                        candidate_value=5,
                        delta=4,
                    )
                ],
                change_summary=summary,
            ),
        }
    )
    report = canonical_report_from_analysis(compared)
    html = canonical_html_for_analysis(compared)
    assert html == project_canonical_html(report)
    assert recorded.finding_id in html
    assert "src/App.java" in html
    assert "ranking_value: 24" in html
    assert explanation in html
    assert "0.400000" in html
    assert "src/Util.java" in html
    assert ">3<" in html
    assert ">5<" in html
    assert "affected_test_count: UNKNOWN" in html
    assert "M13.known_vulnerability" in html
    assert ">1<" in html
    assert ">5<" in html
    assert ">4<" in html
    assert "incompatible comparison" in html
    assert "Compatible baseline" not in html
    assert "Stable" not in html
    assert report.envelope.body.comparison.movement == "insufficient"


def test_report_copies_rule_findings_and_source_path_without_a_rank(tmp_path: Path) -> None:
    finding = RuleFinding.create(
        rule_id="technical_debt.excessive-branching",
        title="Excessive branching",
        description="branch_point_count 17",
        severity=RuleFindingSeverity.MEDIUM,
        category=RuleFindingCategory.MAINTAINABILITY,
        subject_keys=("path:src/App.java",),
        evidence=(
            RuleFindingEvidence(
                evidence_type="symbol",
                source_id="App.score",
                path="src/App.java",
                excerpt="branch_point_count 17",
            ),
        ),
    )
    report_input = ModernizationReportInput(
        analysis_result=AnalysisResult(
            repository=Repository(name="repo", path=tmp_path, files=["src/App.java"]),
        ),
        generated_at_utc=datetime(2026, 9, 27, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=(finding,),
            rules_evaluated=("technical_debt.excessive-branching",),
        ),
    )
    html = canonical_html_for_report(report_input)
    assert "src/App.java" in html
    assert "technical_debt.excessive-branching" in html
    assert "ranking_value" not in html
    assert "m22_records_not_attached" in html
    assert "Engineering Hotspots unavailable" in html
    assert "First run" in html
    assert "no baseline" in html
    assert "Stable" not in html
    assert "health_score: none" in html


def test_embed_keeps_projector_sections() -> None:
    result = _result()
    canonical = canonical_html_for_analysis(result)
    embedded = embed_canonical_views("<html><body><p>customer</p></body></html>", canonical)
    assert "<p>customer</p>" in embedded
    for view_id in _VIEW_IDS:
        assert f'id="{view_id}"' in embedded


def test_sealed_hotspots_are_used_without_a_live_repository() -> None:
    explanation = build_priority_explanation(
        formula_version="M22.v1",
        complexity="3",
        changed_lines="4",
        ranking_value="12",
        subject_id="src/App.java",
        history_window="all_observed_local_commits",
    )
    hotspot = EngineeringHotspot(
        record_id="hotspot:src/App.java",
        subject_id="src/App.java",
        input_state_digest="abc123",
        list_kind=HotspotListKind.COMPLETE_COMPARABLE,
        ranking_value="12",
        history_profile_id="history-90d",
        history_window="all_observed_local_commits",
        contributors=(
            ContributorRecord(
                name="complexity",
                measurement_id="M16",
                measurement_version="v1",
                role=ContributorRole.RANKING,
                value="3",
                evidence_ids=("evidence:m16.function",),
            ),
            ContributorRecord(
                name="churn",
                measurement_id="M24",
                measurement_version="v1",
                role=ContributorRole.RANKING,
                value="4",
                evidence_ids=("evidence:m16.function",),
            ),
        ),
        evidence_ids=("evidence:m16.function",),
        priority_explanation=explanation,
    )
    ownership = OwnershipConcentration(
        record_id="m25:repo",
        scope=OwnershipScope.REPOSITORY,
        subject_id="repo",
        numerator=1,
        denominator=1,
        serialized_ratio="1.000000",
        history_profile_id="history-90d",
        evidence_ids=("evidence:git",),
        status=ResultStatus.PASS,
        notes="sealed assess records",
    )
    result = AnalysisResult(
        repository=Repository(
            name="missing-repo",
            path=Path("missing-repo"),
            files=["src/App.java"],
        ),
        metadata={
            CANONICAL_HOTSPOTS_KEY: [hotspot.model_dump(mode="json")],
            CANONICAL_OWNERSHIP_KEY: [ownership.model_dump(mode="json")],
            CANONICAL_COVERAGE_KEY: [],
            CANONICAL_FRESHNESS_KEY: [],
        },
    )
    report = canonical_report_from_analysis(result)
    assert report.envelope.body.hotspots[0].ranking_value == "12"
    assert report.envelope.body.ownership[0].serialized_ratio == "1.000000"
    assert Path("missing-repo").exists() is False
