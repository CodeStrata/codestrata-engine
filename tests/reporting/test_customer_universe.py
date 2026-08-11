"""Customer finding/recommendation universe alignment tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from codestrata.domain.findings import Finding as Phase3Finding
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.models import AnalysisResult, Finding, Recommendation, Repository
from codestrata.models.enums import (
    FindingCategory as Phase1FindingCategory,
)
from codestrata.models.enums import (
    FindingSource as Phase1FindingSource,
)
from codestrata.models.enums import (
    Priority,
    RecommendationCategory,
    Risk,
    Severity,
)
from codestrata.models.evidence import Evidence
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.customer_universe import (
    resolve_customer_findings,
    resolve_customer_recommendations,
    write_customer_finding_artifacts,
)
from codestrata.reporting.html_v2.builder import build_customer_report_document
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def _report_input(
    tmp_path: Path,
    *,
    phase1_findings: list[Finding],
    phase1_recommendations: list[Recommendation],
    phase3_findings: list[Phase3Finding] | None = None,
) -> ModernizationReportInput:
    repository = Repository(
        name="spring-petclinic",
        path=tmp_path / "spring-petclinic",
        files=["pom.xml"],
        total_files=1,
    )
    (repository.path).mkdir(parents=True, exist_ok=True)
    analysis = AnalysisResult(
        repository=repository,
        technologies=[],
        findings=phase1_findings,
        recommendations=phase1_recommendations,
        analyzer_version="test",
        duration_ms=1.0,
    )
    evaluation = None
    if phase3_findings is not None:
        evaluation = RuleEvaluationResult.from_findings(
            findings=phase3_findings,
            rules_evaluated=("java-detected",),
            rules_skipped=(),
        )
    return ModernizationReportInput(
        assessment_mode=AssessmentMode.DETERMINISTIC,
        analysis_result=analysis,
        assessment_rule_evaluation=evaluation,
        assessment_recommendation_result=None,
        generated_at_utc="2026-07-21T18:00:00Z",
        report_title="Test",
        organization_name="CodeStrata",
        warnings=(),
        report_artifacts=(),
        highlighted_versions=(),
    )


def test_customer_universe_merges_phase1_and_phase3(tmp_path: Path) -> None:
    phase1 = Finding(
        id=uuid4(),
        rule_id="DEP003",
        title="Evaluate reusable Kubernetes packaging",
        description="Packaging opportunity",
        category=Phase1FindingCategory.CLOUD_READINESS,
        severity=Severity.MEDIUM,
        source=Phase1FindingSource.DETERMINISTIC,
    )
    phase3 = Phase3Finding.create(
        rule_id="java-detected",
        title="Java detected",
        description="Java language present",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.BUILD,
    )
    recommendation = Recommendation(
        id=uuid4(),
        rule_id="DEP003",
        title="Evaluate reusable Kubernetes deployment packaging",
        description="Consider Helm or Kustomize",
        rationale="Cloud packaging signal",
        priority=Priority.MEDIUM,
        category=RecommendationCategory.CLOUD,
        risk=Risk.LOW,
    )
    report_input = _report_input(
        tmp_path,
        phase1_findings=[phase1],
        phase1_recommendations=[recommendation],
        phase3_findings=[phase3],
    )
    findings = resolve_customer_findings(report_input)
    recommendations = resolve_customer_recommendations(report_input)
    assert len(findings) == 2
    assert len(recommendations) == 1

    document = build_assessment_json_document(report_input)
    summary = document["assessment"]["summary"]
    assert summary["finding_count"] == 2
    assert summary["recommendation_count"] == 1
    assert len(document["assessment"]["findings"]) == 2
    assert len(document["assessment"]["deterministic_recommendations"]) == 1

    html_doc = build_customer_report_document(report_input)
    assert html_doc.summary.total_findings == 2
    assert html_doc.summary.total_recommendations == 1
    assert len(html_doc.findings) == 2
    assert len(html_doc.recommendations) == 1
    assert html_doc.recommendations[0].title == recommendation.title

    write_customer_finding_artifacts(report_input, tmp_path / "run")
    findings_json = (tmp_path / "run" / "findings.json").read_text(encoding="utf-8")
    recommendations_json = (tmp_path / "run" / "recommendations.json").read_text(
        encoding="utf-8"
    )
    assert '"finding_count": 2' in findings_json
    assert '"recommendation_count": 1' in recommendations_json
    assert "Evaluate reusable Kubernetes deployment packaging" in recommendations_json


def test_related_finding_ids_aligned_to_final_customer_findings(tmp_path: Path) -> None:
    """Dedupe survivors keep traceability; unknown IDs are dropped."""

    kept = Finding(
        id=uuid4(),
        rule_id="SEC001",
        title="Sensitive configuration",
        description="First evidence row",
        category=Phase1FindingCategory.SECURITY,
        severity=Severity.HIGH,
        source=Phase1FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path=".env", description="env A")],
    )
    dropped = Finding(
        id=uuid4(),
        rule_id="SEC001",
        title="Sensitive configuration",
        description="Second evidence row",
        category=Phase1FindingCategory.SECURITY,
        severity=Severity.HIGH,
        source=Phase1FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path=".env.local", description="env B")],
    )
    unique = Finding(
        id=uuid4(),
        rule_id="ARCH001",
        title="Architecture components detected",
        description="Structural signal",
        category=Phase1FindingCategory.ARCHITECTURE,
        severity=Severity.LOW,
        source=Phase1FindingSource.DETERMINISTIC,
    )
    recommendation = Recommendation(
        id=uuid4(),
        rule_id="REC.SEC.001",
        title="Review committed secrets",
        description="Rotate and remove secrets",
        rationale="Sensitive configuration detected",
        priority=Priority.HIGH,
        category=RecommendationCategory.SECURITY,
        risk=Risk.HIGH,
        related_finding_ids=[str(dropped.id), "not-a-finding", str(unique.id)],
    )
    report_input = _report_input(
        tmp_path,
        phase1_findings=[kept, dropped, unique],
        phase1_recommendations=[recommendation],
    )

    findings = resolve_customer_findings(report_input)
    finding_ids = {item.id for item in findings}
    assert len(findings) == 2

    recommendations = resolve_customer_recommendations(report_input)
    assert len(recommendations) == 1
    related = recommendations[0].related_finding_ids
    assert related
    assert set(related) <= finding_ids
    assert "not-a-finding" not in related

    document = build_assessment_json_document(report_input)
    report_finding_ids = {item["id"] for item in document["assessment"]["findings"]}
    for item in document["assessment"]["deterministic_recommendations"]:
        assert set(item["related_finding_ids"]) <= report_finding_ids


def test_shared_rule_findings_with_same_title_are_not_collapsed(tmp_path: Path) -> None:
    """Evidence-scoped finding:* IDs must survive customer-universe merge."""

    first = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal A",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
    )
    # Force distinct stable IDs resembling production evidence-scoped IDs.
    first = first.model_copy(update={"id": "finding:security.credential-literal:aaaa"})
    second = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal B",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.SECURITY,
    )
    second = second.model_copy(update={"id": "finding:security.credential-literal:bbbb"})
    report_input = _report_input(
        tmp_path,
        phase1_findings=[],
        phase1_recommendations=[],
        phase3_findings=[first, second],
    )
    findings = resolve_customer_findings(report_input)
    assert len(findings) == 2
    assert {item.id for item in findings} == {
        "finding:security.credential-literal:aaaa",
        "finding:security.credential-literal:bbbb",
    }
