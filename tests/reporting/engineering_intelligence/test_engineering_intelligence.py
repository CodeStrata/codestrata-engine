"""Epic 3 Slice 3.10 — Engineering Intelligence Summary tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    RuleEvaluationResult,
)
from codestrata.domain.recommendations import (
    Recommendation,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
)
from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceLocation,
    EvidenceRef,
)
from codestrata.models import (
    AnalysisResult,
    Repository,
    RepositoryFacts,
    StructureFacts,
)
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.engineering_intelligence import (
    build_engineering_intelligence,
    scrub_soft_engineering_claims,
)
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    assessment_head_anchor,
)
from codestrata.reporting.html_v2.models import AssessmentHeadSectionView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

_FORBIDDEN = (
    "healthy engineering organization",
    "production ready",
    "modernization ready",
    "cloud ready",
    "ai ready",
    "enterprise ready",
    "no issues found",
    "no security issues",
)


def _assert_no_forbidden(text: str) -> None:
    lowered = text.lower()
    sanitized = (
        lowered.replace("ai readiness", "")
        .replace("cloud readiness", "")
        .replace("does not establish", "")
        .replace("engineering intelligence summary", "")
    )
    for phrase in _FORBIDDEN:
        assert phrase not in sanitized, f"forbidden claim present: {phrase}"


def _head(
    *,
    head: str,
    title: str,
    anchor: str,
    status: str = "assessed",
    findings: int = 0,
    recommendations: int = 0,
    confidence: str = "high",
    evidence_state: str = "available",
    pa_ids: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> AssessmentHeadSectionView:
    return AssessmentHeadSectionView(
        head=head,
        title=title,
        anchor=anchor,
        status=status,
        status_label=status.replace("_", " ").title(),
        findings_count=findings,
        recommendations_count=recommendations,
        evidence_state=evidence_state,
        confidence=confidence,
        confidence_label={
            "high": "High confidence",
            "moderate": "Moderate confidence",
            "limited": "Limited confidence",
            "unavailable": "Confidence unavailable",
        }.get(confidence, "Confidence unavailable"),
        related_priority_action_ids=pa_ids,
        limitations=limitations,
        pack_content_available=True,
    )


def test_build_aggregates_heads_and_weakest_confidence() -> None:
    heads = (
        _head(
            head="security_intelligence",
            title="Security Intelligence",
            anchor="security-intelligence",
            findings=2,
            recommendations=1,
            confidence="high",
            pa_ids=("pa-1",),
            limitations=("Repository evidence only.",),
        ),
        _head(
            head="dependency_intelligence",
            title="Dependency Intelligence",
            anchor="dependency-intelligence",
            findings=1,
            recommendations=1,
            confidence="limited",
            pa_ids=("pa-2",),
        ),
        _head(
            head="cloud_readiness",
            title="Cloud Readiness",
            anchor="cloud-readiness",
            status="not_enabled",
            confidence="unavailable",
            evidence_state="unavailable",
        ),
    )
    actions = (
        RecommendationView(
            recommendation_id="pa-1",
            title="Remediate credentials",
            summary="Rotate",
            rationale="Security",
            priority="high",
            category="security",
            presentation_bucket="near_term",
            action_type="recommendation_backed",
        ),
        RecommendationView(
            recommendation_id="pa-2",
            title="Pin versions",
            summary="Pin",
            rationale="Dependency",
            priority="medium",
            category="dependency",
            presentation_bucket="later",
            action_type="recommendation_backed",
        ),
    )
    intel = build_engineering_intelligence(
        assessment_heads=heads,
        priority_actions=actions,
        priority_actions_total=2,
        highest_finding_severity="high",
    )
    assert len(intel.head_summaries) == 3
    assert intel.total_findings == 3
    assert intel.total_recommendations == 2
    assert intel.priority_action_total == 2
    assert intel.confidence == "limited"
    assert intel.confidence_label == "Limited confidence"
    assert any(row.label == "high" and row.count == 1 for row in intel.priority_by_priority)
    assert any(
        row.label == "near_term" and row.count == 1 for row in intel.priority_by_horizon
    )
    joined = " ".join(intel.limitations).lower()
    assert "based only on enabled assessment heads" in joined
    assert "runtime behavior not evaluated" in joined
    assert "disabled heads reduce completeness" in joined
    assert "repository evidence only" in joined
    assert "not enabled or not available" in joined
    _assert_no_forbidden(intel.status_summary)
    _assert_no_forbidden(" ".join(intel.observations))
    _assert_no_forbidden(" ".join(intel.limitations))


def test_soft_claims_scrubbed() -> None:
    scrubbed = scrub_soft_engineering_claims(
        "Healthy engineering organization that is production ready and cloud ready.",
        fallback="safe",
    )
    assert scrubbed == "safe"
    ok = scrub_soft_engineering_claims(
        "The assessment summarizes deterministic observations from the enabled "
        "assessment heads.",
        fallback="safe",
    )
    assert "summarizes deterministic observations" in ok.lower()


def test_html_engineering_intelligence_summary(tmp_path: Path) -> None:
    ref = EvidenceRef(
        evidence_id="ev:secret-1",
        location=EvidenceLocation(path="src/App.py", line_start=4, line_end=6),
    )
    finding = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="Found credential",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("path:src/App.py",),
        evidence=(
            FindingEvidence(
                evidence_type="file",
                source_id="src",
                path="src/App.py",
                excerpt="***",
            ),
        ),
        evidence_refs=(ref,),
        primary_evidence_id="ev:secret-1",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )
    recommendation = Recommendation.create(
        provider_id="codestrata-rec-secret",
        title="Remediate credentials",
        summary="Rotate exposed credentials",
        rationale="Security risk",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.GOVERNANCE,
        related_finding_ids=(finding.id,),
        supporting_finding_ids=(finding.id,),
        primary_finding_id=finding.id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        actions=(
            RecommendationAction(order=1, title="Rotate", description="Rotate secret"),
        ),
        subject_keys=("repo",),
    )
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["src/App.py"],
            total_files=1,
        ),
        technologies=[],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=1,
                source_file_count=1,
                test_file_count=0,
            )
        ),
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=(finding,),
            rules_evaluated=("security.credential-literal",),
        ),
        assessment_recommendation_result=RecommendationResult.from_recommendations(
            recommendations=(recommendation,),
            providers_evaluated=("codestrata-rec-secret",),
        ),
    )
    document = build_html_report_view_model(report_input)
    assert document.engineering_intelligence is not None
    html = HtmlReportRenderer().render(document)

    assert 'id="executive-summary"' in html
    assert 'id="engineering-intelligence-summary"' in html
    assert html.find('id="executive-summary"') < html.find(
        'id="engineering-intelligence-summary"'
    )
    assert "Overall assessment status" in html
    assert "Assessment heads assessed" in html
    assert "High-level engineering observations" in html
    assert "Cross-head summary" in html
    assert "Priority Action summary" in html
    assert "Coverage" in html
    assert "Confidence" in html
    assert "Limitations" in html
    assert 'data-canonical="coverage-confidence-limitations"' in html
    assert 'href="#priority-actions"' in html
    assert 'href="#security-intelligence"' in html

    # No duplicated recommendation/roadmap detail lists inside EIS.
    eis_start = html.find('id="engineering-intelligence-summary"')
    eis_end = html.find('id="key-takeaways"')
    eis_body = html[eis_start:eis_end]
    assert "Stabilize → Secure → Modernize → Optimize" not in eis_body
    assert eis_body.count("item-card recommendation") == 0
    assert "presentation:finding:" not in html

    for head in ASSESSMENT_RESULT_HEADS:
        anchor = assessment_head_anchor(head)
        assert f'id="{anchor}"' in html
        assert len(re.findall(rf'id="{re.escape(anchor)}"', html)) == 1

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    _assert_no_forbidden(eis_body)
    ordered = [entry.section_id for entry in document.outline]
    assert ordered.index("executive-summary") < ordered.index(
        "engineering-intelligence-summary"
    )
