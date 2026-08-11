"""Slice 5.11 — customer-universe consolidation and reference remapping."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from codestrata.domain.findings import Finding as Phase3Finding
from codestrata.domain.findings import FindingCategory, FindingEvidence, FindingSeverity
from codestrata.domain.findings.models import RuleEvaluationResult
from codestrata.domain.recommendations import Recommendation as Phase3Recommendation
from codestrata.domain.recommendations import RecommendationResult
from codestrata.domain.recommendations.enums import (
    RecommendationCategory,
    RecommendationPriority,
)
from codestrata.domain.recommendations.models import RecommendationAction
from codestrata.models import AnalysisResult, Finding as Phase1Finding, Recommendation, Repository
from codestrata.models.enums import (
    FindingCategory as Phase1FindingCategory,
)
from codestrata.models.enums import (
    FindingSource as Phase1FindingSource,
)
from codestrata.models.enums import Severity
from codestrata.models.evidence import Evidence
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.customer_universe import (
    resolve_customer_findings,
    resolve_customer_recommendations,
)
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def _report_input(
    tmp_path: Path,
    *,
    phase1_findings: list | None = None,
    phase1_recommendations: list | None = None,
    phase3_findings: list | None = None,
    phase3_recommendations: list | None = None,
) -> ModernizationReportInput:
    repository = Repository(
        name="demo",
        path=tmp_path / "demo",
        files=["pom.xml"],
        total_files=1,
    )
    repository.path.mkdir(parents=True, exist_ok=True)
    analysis = AnalysisResult(
        repository=repository,
        technologies=[],
        findings=list(phase1_findings or []),
        recommendations=list(phase1_recommendations or []),
        analyzer_version="test",
        duration_ms=1.0,
    )
    evaluation = None
    if phase3_findings is not None:
        evaluation = RuleEvaluationResult.from_findings(
            findings=phase3_findings,
            rules_evaluated=tuple(sorted({item.rule_id for item in phase3_findings})),
        )
    rec_result = None
    if phase3_recommendations is not None:
        rec_result = RecommendationResult.from_recommendations(
            recommendations=tuple(phase3_recommendations),
            providers_evaluated=("builtin.security.credential",),
        )
    return ModernizationReportInput(
        assessment_mode=AssessmentMode.DETERMINISTIC,
        analysis_result=analysis,
        assessment_rule_evaluation=evaluation,
        assessment_recommendation_result=rec_result,
        generated_at_utc="2026-08-01T18:00:00Z",
        report_title="Test",
        organization_name="CodeStrata",
        warnings=(),
        report_artifacts=(),
        highlighted_versions=(),
    )


def test_equivalent_phase3_findings_consolidate_in_customer_universe(tmp_path: Path) -> None:
    first = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal A",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=(
            "security.credential-literal",
            "ev:aaaaaaaaaaaaaaaaaaaaaaaa",
            "src/app.env",
            "API_KEY",
        ),
        evidence=(
            FindingEvidence(evidence_type="config", source_id="API_KEY", path="src/app.env"),
        ),
        metadata={
            "subject_keys": (
                "security.credential-literal,ev:aaaaaaaaaaaaaaaaaaaaaaaa,src/app.env,API_KEY"
            )
        },
    )
    second = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal B",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=(
            "security.credential-literal",
            "ev:bbbbbbbbbbbbbbbbbbbbbbbb",
            "src/app.env",
            "API_KEY",
        ),
        evidence=(
            FindingEvidence(evidence_type="config", source_id="API_KEY", path="src/app.env"),
        ),
        metadata={
            "subject_keys": (
                "security.credential-literal,ev:bbbbbbbbbbbbbbbbbbbbbbbb,src/app.env,API_KEY"
            )
        },
    )
    assert first.id != second.id
    report_input = _report_input(tmp_path, phase3_findings=[first, second])
    findings = resolve_customer_findings(report_input)
    assert len(findings) == 1
    assert findings[0].id in {first.id, second.id}


def test_distinct_conditions_with_same_title_remain_separate(tmp_path: Path) -> None:
    first = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal A",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("security.credential-literal", "ev:aaaaaaaaaaaaaaaaaaaaaaaa", "a.env", "A"),
        evidence=(FindingEvidence(evidence_type="config", source_id="A", path="a.env"),),
        metadata={
            "subject_keys": "security.credential-literal,ev:aaaaaaaaaaaaaaaaaaaaaaaa,a.env,A"
        },
    )
    second = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal B",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.SECURITY,
        subject_keys=("security.credential-literal", "ev:bbbbbbbbbbbbbbbbbbbbbbbb", "b.env", "B"),
        evidence=(FindingEvidence(evidence_type="config", source_id="B", path="b.env"),),
        metadata={
            "subject_keys": "security.credential-literal,ev:bbbbbbbbbbbbbbbbbbbbbbbb,b.env,B"
        },
    )
    report_input = _report_input(tmp_path, phase3_findings=[first, second])
    findings = resolve_customer_findings(report_input)
    assert len(findings) == 2


def test_recommendation_member_ids_remap_to_canonical(tmp_path: Path) -> None:
    first = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal A",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=(
            "security.credential-literal",
            "ev:aaaaaaaaaaaaaaaaaaaaaaaa",
            "src/app.env",
            "API_KEY",
        ),
        evidence=(
            FindingEvidence(evidence_type="config", source_id="API_KEY", path="src/app.env"),
        ),
        metadata={
            "subject_keys": (
                "security.credential-literal,ev:aaaaaaaaaaaaaaaaaaaaaaaa,src/app.env,API_KEY"
            )
        },
    )
    second = Phase3Finding.create(
        rule_id="security.credential-literal",
        title="Credential literal in configuration",
        description="Literal B",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=(
            "security.credential-literal",
            "ev:bbbbbbbbbbbbbbbbbbbbbbbb",
            "src/app.env",
            "API_KEY",
        ),
        evidence=(
            FindingEvidence(evidence_type="config", source_id="API_KEY", path="src/app.env"),
        ),
        metadata={
            "subject_keys": (
                "security.credential-literal,ev:bbbbbbbbbbbbbbbbbbbbbbbb,src/app.env,API_KEY"
            )
        },
    )
    recommendation = Phase3Recommendation.create(
        provider_id="builtin.security.credential",
        title="Remove credential literals",
        summary="Rotate and remove",
        rationale="credential findings",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.MODERNIZATION,
        related_finding_ids=(first.id, second.id),
        supporting_finding_ids=(first.id, second.id),
        primary_finding_id=second.id,
        actions=(
            RecommendationAction(
                order=1,
                title="Rotate credentials",
                description="Rotate and remove committed credential literals",
            ),
        ),
    )
    report_input = _report_input(
        tmp_path,
        phase3_findings=[first, second],
        phase3_recommendations=[recommendation],
    )
    findings = resolve_customer_findings(report_input)
    assert len(findings) == 1
    canonical = findings[0].id
    recommendations = resolve_customer_recommendations(report_input)
    assert len(recommendations) == 1
    related = recommendations[0].related_finding_ids
    supporting = recommendations[0].supporting_finding_ids
    assert related == supporting == (canonical,)
    assert recommendations[0].primary_finding_id == canonical

    document = build_assessment_json_document(report_input)
    report_finding_ids = {item["id"] for item in document["assessment"]["findings"]}
    assert report_finding_ids == {canonical}
    for item in document["assessment"]["deterministic_recommendations"]:
        assert set(item["related_finding_ids"]) <= report_finding_ids


def test_phase1_rule_title_collision_unions_evidence(tmp_path: Path) -> None:
    kept = Phase1Finding(
        id=uuid4(),
        rule_id="SEC001",
        title="Sensitive configuration",
        description="First evidence row",
        category=Phase1FindingCategory.SECURITY,
        severity=Severity.HIGH,
        source=Phase1FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path=".env", description="env A")],
    )
    dropped = Phase1Finding(
        id=uuid4(),
        rule_id="SEC001",
        title="Sensitive configuration",
        description="Second evidence row",
        category=Phase1FindingCategory.SECURITY,
        severity=Severity.HIGH,
        source=Phase1FindingSource.DETERMINISTIC,
        evidence=[Evidence(file_path=".env.local", description="env B")],
    )
    report_input = _report_input(tmp_path, phase1_findings=[kept, dropped])
    findings = resolve_customer_findings(report_input)
    assert len(findings) == 1
    paths = {row.get("file_path") for row in findings[0].evidence}
    assert ".env" in paths
    assert ".env.local" in paths
