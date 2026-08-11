"""Epic 3 Slice 3.11 — canonical Coverage / Confidence / Limitations tests."""

from __future__ import annotations

import inspect
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
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    assessment_head_anchor,
)
from codestrata.reporting.html_v2.coverage_confidence_limitations import (
    CCL_BLOCK_CLASS,
    CONFIDENCE_UNAVAILABLE,
    COVERAGE_UNAVAILABLE,
    LIMITATIONS_UNAVAILABLE,
    dedupe_limitations,
    normalize_confidence_display,
    render_coverage_confidence_limitations,
    simple_coverage_row,
)
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput


def test_normalize_confidence_vocabulary() -> None:
    assert normalize_confidence_display("high") == "High"
    assert normalize_confidence_display(confidence_label="High confidence") == "High"
    assert normalize_confidence_display("moderate") == "Moderate"
    assert normalize_confidence_display("medium") == "Moderate"
    assert normalize_confidence_display("limited") == "Limited"
    assert normalize_confidence_display("low") == "Limited"
    assert normalize_confidence_display("unavailable") == "Unavailable"
    assert normalize_confidence_display(confidence_label="Confidence unavailable") == (
        "Unavailable"
    )
    assert normalize_confidence_display(None, None) == CONFIDENCE_UNAVAILABLE
    for forbidden in ("Strong", "Weak", "Good", "Excellent", "Likely"):
        assert normalize_confidence_display(forbidden) == CONFIDENCE_UNAVAILABLE
    # "Low confidence" normalizes to Limited (never rendered as "Low confidence").
    assert normalize_confidence_display(confidence_label="Low confidence") == "Limited"


def test_dedupe_limitations() -> None:
    merged = dedupe_limitations(
        (
            "Repository evidence only.",
            "repository evidence only.",
            "Runtime behavior not evaluated.",
            "",
            "Repository evidence only.",
        )
    )
    assert merged == (
        "Repository evidence only.",
        "Runtime behavior not evaluated.",
    )


def test_empty_states_render_consistently() -> None:
    html = render_coverage_confidence_limitations(
        coverage_rows=(),
        confidence=None,
        confidence_label=None,
        limitations=(),
    )
    assert 'data-canonical="coverage-confidence-limitations"' in html
    assert f'class="{CCL_BLOCK_CLASS}"' in html
    assert "<h4>Coverage</h4>" in html
    assert "<h4>Confidence</h4>" in html
    assert "<h4>Limitations</h4>" in html
    assert COVERAGE_UNAVAILABLE in html
    assert CONFIDENCE_UNAVAILABLE in html or ">Unavailable<" in html
    assert LIMITATIONS_UNAVAILABLE in html
    # Ordering: Coverage before Confidence before Limitations
    assert html.find("<h4>Coverage</h4>") < html.find("<h4>Confidence</h4>")
    assert html.find("<h4>Confidence</h4>") < html.find("<h4>Limitations</h4>")


def test_coverage_rows_and_limitations_render() -> None:
    html = render_coverage_confidence_limitations(
        coverage_rows=(
            simple_coverage_row(
                label="Security Intelligence",
                status="assessed",
                display="findings: 1",
                note="Assessed",
            ),
        ),
        confidence="high",
        confidence_label="High confidence",
        limitations=("Repository evidence only.", "Repository evidence only."),
    )
    assert "Security Intelligence" in html
    assert ">High<" in html
    assert "Repository evidence only." in html
    assert html.count("Repository evidence only.") == 1


def test_helper_reused_not_copy_pasted() -> None:
    import codestrata.reporting.html_v2.renderer as renderer_mod

    source = inspect.getsource(renderer_mod)
    # Pack-specific coverage headings must no longer be hand-rolled.
    for obsolete in (
        "Architecture coverage",
        "Technical debt coverage",
        "Dependency coverage",
        "Security coverage",
        "Cloud coverage",
        "AI readiness coverage",
        "Overall coverage",
        "Overall confidence",
        "Overall limitations",
        "Inventory limitations",
    ):
        assert obsolete not in source, f"obsolete heading still in renderer: {obsolete}"
    assert source.count("render_coverage_confidence_limitations(") >= 8


def test_html_assessment_heads_end_with_canonical_ccl(tmp_path: Path) -> None:
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
    html = HtmlReportRenderer().render(document)

    assert 'id="engineering-intelligence-summary"' in html
    assert html.count('data-canonical="coverage-confidence-limitations"') >= 2

    # Each assessment-head section contains Coverage → Confidence → Limitations.
    for head in ASSESSMENT_RESULT_HEADS:
        anchor = assessment_head_anchor(head)
        assert f'id="{anchor}"' in html
        start = html.find(f'id="{anchor}"')
        # Section roughly until next assessment-head or roadmap/appendix.
        chunk = html[start : start + 12000]
        cov = chunk.find("<h4>Coverage</h4>")
        conf = chunk.find("<h4>Confidence</h4>")
        lim = chunk.find("<h4>Limitations</h4>")
        assert cov >= 0 and conf >= 0 and lim >= 0, f"missing CCL in {anchor}"
        assert cov < conf < lim, f"CCL order wrong in {anchor}"

    # EIS also uses canonical labels (not Overall *).
    eis = html[
        html.find('id="engineering-intelligence-summary"') : html.find(
            'id="key-takeaways"'
        )
    ]
    assert "<h4>Coverage</h4>" in eis
    assert "<h4>Confidence</h4>" in eis
    assert "<h4>Limitations</h4>" in eis
    assert "Overall coverage" not in eis
    assert "Overall confidence" not in eis

    # Confidence vocabulary in canonical blocks.
    for match in re.findall(
        r'data-group="confidence">\s*<h4>Confidence</h4>\s*<p>([^<]+)</p>',
        html,
    ):
        assert match.strip() in {"High", "Moderate", "Limited", "Unavailable"}

    assert "Strong" not in html
    assert "Excellent" not in html
    assert "Low confidence" not in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
