"""HTML / EIS Assessment-Head Confidence integration (Slice 5.4)."""

from __future__ import annotations

from codestrata.application.assessment_heads.confidence import (
    apply_canonical_head_confidence,
)
from codestrata.reporting.engineering_intelligence.intelligence import (
    build_engineering_intelligence,
)
from codestrata.reporting.html_v2.assessment_heads import AssessmentHead
from codestrata.reporting.html_v2.coverage_confidence_limitations import (
    normalize_confidence_display,
    render_coverage_confidence_limitations,
)
from codestrata.reporting.html_v2.models import (
    AssessmentHeadSectionView,
    FindingView,
)


def _finding(*, level: str, finding_id: str = "f1") -> FindingView:
    return FindingView(
        finding_id=finding_id,
        rule_id="architecture.layer",
        title="Finding",
        description="desc",
        severity="high",
        category="architecture",
        finding_confidence_level=level,
        evidence_completeness="complete",
    )


def test_apply_canonical_head_confidence_replaces_guessed_label() -> None:
    section = AssessmentHeadSectionView(
        head=AssessmentHead.ARCHITECTURE_INTELLIGENCE.value,
        title="Architecture Intelligence",
        anchor="architecture-intelligence",
        status="assessed",
        status_label="Assessed",
        findings_count=2,
        recommendations_count=0,
        evidence_state="available",
        confidence="high",
        confidence_label="High confidence",
        limitations=(),
        findings=(
            _finding(level="high", finding_id="a"),
            _finding(level="moderate", finding_id="b"),
        ),
        recommendations=(),
        related_priority_action_ids=(),
        pack_content_available=True,
    )
    updated = apply_canonical_head_confidence(section, coverage_state="complete")
    assert updated.confidence == "moderate"
    assert updated.assessment_head_confidence is not None
    assert updated.assessment_head_confidence["level"] == "moderate"
    assert "mixed_finding_confidence" in updated.assessment_head_confidence["basis"]


def test_ccl_uses_canonical_head_confidence_only() -> None:
    html = render_coverage_confidence_limitations(
        coverage_rows=(("Architecture signals", "Supported"),),
        confidence="moderate",
        confidence_label="Moderate confidence",
        limitations=("Partial inventory coverage.",),
    )
    assert 'data-group="confidence"' in html
    assert ">Confidence<" in html
    assert normalize_confidence_display("moderate", "Moderate confidence") == "Moderate"
    assert "Finding confidence" not in html
    assert "Rule confidence" not in html


def test_eis_weakest_contributing_head_wins() -> None:
    heads = (
        AssessmentHeadSectionView(
            head=AssessmentHead.ARCHITECTURE_INTELLIGENCE.value,
            title="Architecture Intelligence",
            anchor="architecture-intelligence",
            status="assessed",
            status_label="Assessed",
            findings_count=1,
            recommendations_count=0,
            evidence_state="available",
            confidence="high",
            confidence_label="High confidence",
            limitations=(),
            findings=(_finding(level="high"),),
            recommendations=(),
            related_priority_action_ids=(),
            pack_content_available=True,
            assessment_head_confidence={"level": "high"},
        ),
        AssessmentHeadSectionView(
            head=AssessmentHead.SECURITY_INTELLIGENCE.value,
            title="Security Intelligence",
            anchor="security-intelligence",
            status="assessed",
            status_label="Assessed",
            findings_count=1,
            recommendations_count=0,
            evidence_state="available",
            confidence="limited",
            confidence_label="Limited confidence",
            limitations=("Deferred mapping.",),
            findings=(_finding(level="limited", finding_id="s1"),),
            recommendations=(),
            related_priority_action_ids=(),
            pack_content_available=True,
            assessment_head_confidence={"level": "limited"},
        ),
        AssessmentHeadSectionView(
            head=AssessmentHead.CLOUD_READINESS.value,
            title="Cloud Readiness",
            anchor="cloud-readiness",
            status="not_enabled",
            status_label="Not enabled",
            findings_count=0,
            recommendations_count=0,
            evidence_state="unavailable",
            confidence="unavailable",
            confidence_label="Confidence unavailable",
            limitations=(),
            findings=(),
            recommendations=(),
            related_priority_action_ids=(),
            pack_content_available=False,
            assessment_head_confidence={"level": "unavailable"},
        ),
    )
    intel = build_engineering_intelligence(assessment_heads=heads)
    assert intel.confidence == "limited"
    assert "Limited" in intel.confidence_label
