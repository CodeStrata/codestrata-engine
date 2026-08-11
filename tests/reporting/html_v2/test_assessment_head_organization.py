"""Epic 3 Slice 3.1 — assessment-head report organization tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from codestrata.models import (
    AnalysisResult,
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
)
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.assessment_head_grouping import (
    classify_finding_head,
    classify_recommendation_head,
)
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    AssessmentHead,
    all_assessment_heads,
    assessment_head_anchor,
    assessment_head_order,
    assessment_head_title,
)
from codestrata.reporting.html_v2.models import FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def _finding_view(
    *,
    finding_id: str,
    category: str,
    rule_id: str = "rule.demo",
) -> FindingView:
    return FindingView(
        finding_id=finding_id,
        rule_id=rule_id,
        title=f"Title {finding_id}",
        description="desc",
        severity="high",
        category=category,
    )


def _recommendation_view(
    *,
    recommendation_id: str,
    category: str,
    related_finding_ids: tuple[str, ...] = (),
    primary_finding_id: str | None = None,
) -> RecommendationView:
    return RecommendationView(
        recommendation_id=recommendation_id,
        title=f"Rec {recommendation_id}",
        summary="summary",
        rationale="rationale",
        priority="high",
        category=category,
        related_finding_ids=related_finding_ids,
        primary_finding_id=primary_finding_id,
    )


def test_assessment_head_contract_stable() -> None:
    heads = all_assessment_heads()
    assert AssessmentHead.ENGINEERING_INTELLIGENCE in heads
    assert ASSESSMENT_RESULT_HEADS == (
        AssessmentHead.TECHNOLOGY_INVENTORY,
        AssessmentHead.ARCHITECTURE_INTELLIGENCE,
        AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE,
        AssessmentHead.DEPENDENCY_INTELLIGENCE,
        AssessmentHead.SECURITY_INTELLIGENCE,
        AssessmentHead.CLOUD_READINESS,
        AssessmentHead.AI_READINESS,
        AssessmentHead.MODERNIZATION_ASSESSMENT,
    )
    assert assessment_head_title(AssessmentHead.SECURITY_INTELLIGENCE) == "Security Intelligence"
    assert assessment_head_anchor(AssessmentHead.SECURITY_INTELLIGENCE) == "security-intelligence"
    orders = [assessment_head_order(h) for h in ASSESSMENT_RESULT_HEADS]
    assert orders == sorted(orders)


def test_finding_grouping_uses_category_not_title() -> None:
    security = _finding_view(
        finding_id="f-sec",
        category="security",
        rule_id="other.prefix",
    )
    # Title contains "dependency" but category is security — must stay Security.
    security = security.model_copy(update={"title": "dependency version drift"})
    assert classify_finding_head(security) is AssessmentHead.SECURITY_INTELLIGENCE

    dependency = _finding_view(
        finding_id="f-dep",
        category="dependency",
        rule_id="dependency.unlocked",
    )
    assert classify_finding_head(dependency) is AssessmentHead.DEPENDENCY_INTELLIGENCE

    debt = _finding_view(finding_id="f-td", category="technical_debt")
    assert classify_finding_head(debt) is AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE

    architecture = _finding_view(finding_id="f-arch", category="architecture")
    assert classify_finding_head(architecture) is AssessmentHead.ARCHITECTURE_INTELLIGENCE

    unknown = _finding_view(finding_id="f-unk", category="testing", rule_id="testing.skipped")
    assert classify_finding_head(unknown) is None


def test_recommendation_follows_finding_head() -> None:
    finding_heads = {
        "f-sec": AssessmentHead.SECURITY_INTELLIGENCE,
        "f-dep": AssessmentHead.DEPENDENCY_INTELLIGENCE,
    }
    rec = _recommendation_view(
        recommendation_id="r1",
        category="unknown",
        related_finding_ids=("f-sec",),
        primary_finding_id="f-sec",
    )
    assert (
        classify_recommendation_head(rec, finding_heads=finding_heads)
        is AssessmentHead.SECURITY_INTELLIGENCE
    )


def _analysis(tmp_path: Path, findings: list[Finding], recommendations: list[Recommendation]) -> AnalysisResult:
    return AnalysisResult(
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
        findings=findings,
        recommendations=recommendations,
    )


def test_report_hierarchy_and_toc_anchors(tmp_path: Path) -> None:
    findings = [
        Finding(
            rule_id="security.credential-literal",
            title="Hard-coded credential",
            description="Credential literal",
            severity=Severity.HIGH,
            category=FindingCategory.SECURITY,
            source=FindingSource.DETERMINISTIC,
            evidence=[],
        ),
        Finding(
            rule_id="testing.disabled",
            title="Disabled tests",
            description="Skipped tests",
            severity=Severity.MEDIUM,
            category=FindingCategory.TESTING,
            source=FindingSource.DETERMINISTIC,
            evidence=[],
        ),
    ]
    recommendations = [
        Recommendation(
            rule_id="rec.rotate-credential",
            title="Rotate credential",
            description="Remove literal",
            rationale="Credential material must not be committed.",
            priority=Priority.HIGH,
            category=RecommendationCategory.SECURITY,
            risk=Risk.HIGH,
            related_finding_ids=[],
            actions=["Rotate"],
        )
    ]
    report_input = ModernizationReportInput(
        analysis_result=_analysis(tmp_path, findings, recommendations),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )
    document = build_html_report_view_model(report_input)
    html = HtmlReportRenderer().render(document)

    for head in ASSESSMENT_RESULT_HEADS:
        anchor = assessment_head_anchor(head)
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html

    assert 'id="engineering-intelligence-summary"' in html
    assert 'id="executive-summary"' in html
    assert html.find('id="executive-summary"') < html.find(
        'id="engineering-intelligence-summary"'
    )
    assert 'id="assessment-results"' in html
    assert 'id="leadership-verdict"' in html
    assert 'id="priority-actions"' in html
    assert 'id="technical-appendix"' in html

    # No duplicate section anchors for assessment heads.
    for head in ASSESSMENT_RESULT_HEADS:
        anchor = assessment_head_anchor(head)
        assert len(re.findall(rf'id="{re.escape(anchor)}"', html)) == 1

    # Security finding grouped under Security Intelligence; unknown retained.
    security_head = next(
        s for s in document.assessment_heads if s.head == AssessmentHead.SECURITY_INTELLIGENCE.value
    )
    assert any(f.finding_id for f in security_head.findings)
    assert document.unclassified_findings
    assert "could not yet be assigned" in document.unclassified_limitation
    assert "Unclassified" in html or "could not yet be assigned" in html

    # Unsupported conclusions must not appear for unassessed heads.
    assert "No security issues" not in html
    assert "Cloud ready" not in html
    assert "AI ready" not in html
    assert "Healthy" not in html

    # Coverage placeholders present (Slice 3.11 canonical vocabulary).
    assert (
        "Unavailable" in html
        or "High" in html
        or "Limited" in html
        or "Moderate" in html
        or "Confidence unavailable" in html
        or "High confidence" in html
        or "Limited confidence" in html
    )
    assert "Assessed" in html or "Not available" in html or "Partially assessed" in html

    # Schema / IDs unchanged contract surface.
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"


def test_zero_findings_not_healthy_label(tmp_path: Path) -> None:
    report_input = ModernizationReportInput(
        analysis_result=_analysis(tmp_path, [], []),
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )
    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert "No issues found" not in html
    assert "Cloud ready" not in html
    assert "AI ready" not in html
    # Status language may include Assessed/Not available — never Healthy.
    assert re.search(r"\bHealthy\b", html) is None
