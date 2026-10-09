"""R2-P03 — four-outcome Engineering Health projection."""

from __future__ import annotations

from codestrata.domain.contracts.enums import OutcomeFamily
from codestrata.reporting.engineering_health.projection import (
    DISPLAY_INSUFFICIENT_EVIDENCE,
    DISPLAY_NEEDS_ATTENTION,
    DISPLAY_NO_MATERIAL_ISSUES,
    DISPLAY_NOT_APPLICABLE,
    SUPPORTING_CONTEXT_GIT,
    apply_engineering_health_projection,
    map_engineering_health_display_label,
)
from codestrata.reporting.html_v2.assessment_heads import (
    ENGINEERING_HEALTH_HEADLINES,
    AssessmentHead,
    AssessmentHeadRole,
)
from codestrata.reporting.html_v2.models import AssessmentHeadSectionView


def _section(
    *,
    head: AssessmentHead,
    status: str = "assessed",
    status_label: str = "Succeeded",
    findings_count: int = 0,
    coverage_status: str | None = "unavailable",
) -> AssessmentHeadSectionView:
    coverage = None if coverage_status is None else {"status": coverage_status}
    return AssessmentHeadSectionView(
        head=head.value,
        title=head.value,
        anchor=head.value.replace("_", "-"),
        status=status,
        status_label=status_label,
        findings_count=findings_count,
        recommendations_count=0,
        assessment_coverage=coverage,
        pack_content_available=status == "assessed",
    )


def test_public_outcome_families_unchanged() -> None:
    assert [member.value for member in OutcomeFamily] == [
        "architecture",
        "security",
        "quality",
        "maintainability",
    ]


def test_headlines_are_exactly_four_and_include_quality() -> None:
    assert len(ENGINEERING_HEALTH_HEADLINES) == 4
    assert AssessmentHead.QUALITY_INTELLIGENCE in ENGINEERING_HEALTH_HEADLINES
    assert AssessmentHead.CLOUD_READINESS not in ENGINEERING_HEALTH_HEADLINES
    assert AssessmentHead.AI_READINESS not in ENGINEERING_HEALTH_HEADLINES
    assert AssessmentHead.MODERNIZATION_ASSESSMENT not in ENGINEERING_HEALTH_HEADLINES
    assert AssessmentHead.TECHNOLOGY_INVENTORY not in ENGINEERING_HEALTH_HEADLINES
    assert AssessmentHead.DEPENDENCY_INTELLIGENCE not in ENGINEERING_HEALTH_HEADLINES


def test_git_is_supporting_context_not_a_headline() -> None:
    assert SUPPORTING_CONTEXT_GIT == "git"
    assert SUPPORTING_CONTEXT_GIT not in {head.value for head in ENGINEERING_HEALTH_HEADLINES}


def test_display_labels_do_not_invent_canonical_enums() -> None:
    assert map_engineering_health_display_label(
        coverage_status="unavailable",
        finding_count=0,
        execution_status="assessed",
    ) == DISPLAY_INSUFFICIENT_EVIDENCE
    assert map_engineering_health_display_label(
        coverage_status="complete",
        finding_count=0,
        execution_status="assessed",
    ) == DISPLAY_NO_MATERIAL_ISSUES
    assert map_engineering_health_display_label(
        coverage_status="complete",
        finding_count=2,
        execution_status="assessed",
    ) == DISPLAY_NEEDS_ATTENTION
    assert map_engineering_health_display_label(
        coverage_status="disabled",
        finding_count=0,
        execution_status="not_enabled",
    ) == DISPLAY_NOT_APPLICABLE
    assert map_engineering_health_display_label(
        coverage_status="partial",
        finding_count=0,
        execution_status="assessed",
    ) == DISPLAY_INSUFFICIENT_EVIDENCE
    assert map_engineering_health_display_label(
        coverage_status="complete",
        finding_count=0,
        execution_status="assessed",
        evidence_sufficient=False,
    ) == DISPLAY_INSUFFICIENT_EVIDENCE
    assert map_engineering_health_display_label(
        coverage_status="complete",
        finding_count=0,
        execution_status="assessed",
        cannot_prove_clean=True,
    ) == DISPLAY_INSUFFICIENT_EVIDENCE
    assert map_engineering_health_display_label(
        coverage_status="complete",
        finding_count=2,
        execution_status="succeeded",
        evidence_sufficient=False,
    ) == DISPLAY_INSUFFICIENT_EVIDENCE
    assert map_engineering_health_display_label(
        coverage_status="complete",
        finding_count=1,
        execution_status="failed",
    ) == DISPLAY_INSUFFICIENT_EVIDENCE


def test_projection_strips_succeeded_when_coverage_is_unavailable() -> None:
    projected = apply_engineering_health_projection(
        (
            _section(
                head=AssessmentHead.SECURITY_INTELLIGENCE,
                status_label="Succeeded",
                coverage_status="unavailable",
            ),
        )
    )
    assert len(projected) == 1
    assert projected[0].role == AssessmentHeadRole.HEADLINE
    assert projected[0].outcome_family == "security"
    assert projected[0].display_label == DISPLAY_INSUFFICIENT_EVIDENCE
    assert projected[0].status_label != "Succeeded"
    assert projected[0].status_label.lower() not in {"complete", "succeeded", "success"}
    assert projected[0].status != "assessed"


def test_quality_head_is_first_class_projection() -> None:
    projected = apply_engineering_health_projection(
        (
            _section(
                head=AssessmentHead.QUALITY_INTELLIGENCE,
                findings_count=1,
                coverage_status="partial",
            ),
        )
    )
    assert projected[0].role == AssessmentHeadRole.HEADLINE
    assert projected[0].outcome_family == "quality"
    assert projected[0].display_label == DISPLAY_NEEDS_ATTENTION
