"""Tests for the provider-neutral AI recommendation contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
)
from codestrata.ai.recommendations import (
    AI_RECOMMENDATION_SCHEMA_VERSION,
    AIRecommendation,
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
    AIRecommendationResult,
    AIRecommendationValidationError,
    EvidenceCoverage,
    ModernizationPhase,
    ai_recommendation_result_from_json,
    ai_recommendation_result_to_json,
    validate_recommendation_result,
)


def _context(
    *rule_ids: str, truncated: bool = False, original_count: int | None = None
) -> LLMAnalysisContext:
    findings = [
        LLMFindingEvidence(
            rule_id=rule_id,
            title=f"Finding {rule_id}",
            category="security",
            severity="high",
            summary=f"Summary for {rule_id}",
            evidence_truncation=LLMSectionTruncation(
                truncated=False,
                original_count=0,
                included_count=0,
            ),
        )
        for rule_id in rule_ids
    ]
    count = len(findings)
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample",
            source_type="github",
            file_count=1,
        ),
        metrics=LLMMetricsContext(
            finding_count=original_count if original_count is not None else count,
            technology_count=0,
        ),
        findings=findings,
        findings_truncation=LLMSectionTruncation(
            truncated=truncated,
            original_count=original_count if original_count is not None else count,
            included_count=count,
        ),
    )


def _recommendation(
    recommendation_id: str,
    *,
    related: list[str] | None = None,
    dependencies: list[str] | None = None,
    actions: list[str] | None = None,
    priority: AIRecommendationPriority = AIRecommendationPriority.HIGH,
) -> AIRecommendation:
    return AIRecommendation(
        recommendation_id=recommendation_id,
        title=f"Title {recommendation_id}",
        description=f"Description {recommendation_id}",
        rationale=f"Rationale {recommendation_id}",
        priority=priority,
        effort=AIRecommendationEffort.MEDIUM,
        impact=AIRecommendationImpact.HIGH,
        confidence=AIRecommendationConfidence.MEDIUM,
        related_finding_ids=related or [],
        suggested_actions=actions or ["Do the work"],
        dependencies=dependencies or [],
    )


def _coverage(
    *,
    total: int,
    considered: int,
    referenced: int,
    truncated: bool = False,
) -> EvidenceCoverage:
    percentage = 0.0 if considered == 0 else round(100.0 * referenced / considered, 2)
    return EvidenceCoverage(
        total_findings=total,
        findings_considered=considered,
        findings_referenced=referenced,
        coverage_percentage=percentage,
        input_truncated=truncated,
    )


def _complete_result() -> AIRecommendationResult:
    return AIRecommendationResult(
        executive_summary="Executive summary of modernization opportunities.",
        overall_assessment="The application is moderately ready for modernization.",
        key_risks=["Secret exposure", "Missing tests"],
        recommendations=[
            _recommendation(
                "AI-REC-001",
                related=["SEC001"],
                actions=["Rotate credentials", "Add scanning"],
            ),
            _recommendation(
                "AI-REC-002",
                related=["TEST001"],
                dependencies=["AI-REC-001"],
                priority=AIRecommendationPriority.MEDIUM,
                actions=["Add unit tests"],
            ),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Address critical security gaps",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Reduced secret risk"],
            ),
            ModernizationPhase(
                phase=2,
                name="Harden quality",
                objective="Improve test coverage",
                recommendations=["AI-REC-002"],
                expected_outcomes=["Safer refactors"],
            ),
        ],
        evidence_coverage=_coverage(total=2, considered=2, referenced=2),
        limitations=["No runtime profiling data was available."],
    )


def test_complete_valid_contract() -> None:
    result = _complete_result()
    context = _context("SEC001", "TEST001")
    validated = validate_recommendation_result(result, context)
    assert validated.schema_version == AI_RECOMMENDATION_SCHEMA_VERSION
    assert len(validated.recommendations) == 2
    assert len(validated.modernization_phases) == 2


def test_minimal_valid_contract() -> None:
    result = AIRecommendationResult(
        executive_summary="Minimal summary.",
        overall_assessment="Minimal assessment.",
        evidence_coverage=_coverage(total=0, considered=0, referenced=0),
    )
    assert result.recommendations == []
    assert result.modernization_phases == []
    assert result.key_risks == []
    assert result.limitations == []


def test_immutability() -> None:
    result = _complete_result()
    field_name = "executive_summary"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(result, field_name, "changed")
    recommendation = result.recommendations[0]
    title_field = "title"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(recommendation, title_field, "changed")


def test_deterministic_serialization() -> None:
    first = ai_recommendation_result_to_json(_complete_result())
    second = ai_recommendation_result_to_json(_complete_result())
    assert first == second


def test_json_round_trip() -> None:
    result = _complete_result()
    restored = ai_recommendation_result_from_json(ai_recommendation_result_to_json(result))
    assert restored == result


def test_duplicate_recommendation_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="unique"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[
                _recommendation("AI-REC-001"),
                _recommendation("AI-REC-001"),
            ],
            evidence_coverage=_coverage(total=0, considered=0, referenced=0),
        )


def test_invalid_finding_references_rejected() -> None:
    result = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        recommendations=[_recommendation("AI-REC-001", related=["MISSING"])],
        evidence_coverage=_coverage(total=1, considered=1, referenced=1),
    )
    with pytest.raises(AIRecommendationValidationError, match="related_finding_ids"):
        validate_recommendation_result(result, _context("SEC001"))


def test_invalid_phase_recommendation_references_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown recommendation IDs"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[_recommendation("AI-REC-001")],
            modernization_phases=[
                ModernizationPhase(
                    phase=1,
                    name="Phase",
                    objective="Objective",
                    recommendations=["AI-REC-999"],
                )
            ],
            evidence_coverage=_coverage(total=0, considered=0, referenced=0),
        )


def test_invalid_evidence_coverage_bounds_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverage(
            total_findings=-1,
            findings_considered=0,
            findings_referenced=0,
            coverage_percentage=0.0,
        )

    with pytest.raises(ValidationError):
        EvidenceCoverage(
            total_findings=2,
            findings_considered=1,
            findings_referenced=0,
            coverage_percentage=150.0,
        )


def test_enum_validation() -> None:
    with pytest.raises(ValidationError):
        AIRecommendation(
            recommendation_id="rec-1",
            title="Title",
            description="Description",
            rationale="Rationale",
            priority="urgent",  # type: ignore[arg-type]
            effort=AIRecommendationEffort.SMALL,
            impact=AIRecommendationImpact.LOW,
            confidence=AIRecommendationConfidence.LOW,
        )


def test_stable_ordering() -> None:
    result = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        key_risks=["zeta", "alpha", "alpha"],
        limitations=["late", "early"],
        recommendations=[
            _recommendation(
                "AI-REC-002",
                related=["B001", "A001"],
                actions=["zeta", "alpha"],
                dependencies=["AI-REC-001"],
            ),
            _recommendation("AI-REC-001", related=["A001"]),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=2,
                name="Second",
                objective="Two",
                recommendations=["AI-REC-002"],
                expected_outcomes=["z", "a"],
            ),
            ModernizationPhase(
                phase=1,
                name="First",
                objective="One",
                recommendations=["AI-REC-001"],
            ),
        ],
        evidence_coverage=_coverage(total=2, considered=2, referenced=2),
    )

    assert [item.recommendation_id for item in result.recommendations] == [
        "AI-REC-001",
        "AI-REC-002",
    ]
    assert [item.phase for item in result.modernization_phases] == [1, 2]
    assert result.key_risks == ["alpha", "zeta"]
    assert result.limitations == ["early", "late"]
    assert result.recommendations[1].related_finding_ids == ["A001", "B001"]
    assert result.recommendations[1].suggested_actions == ["alpha", "zeta"]
    assert result.modernization_phases[1].expected_outcomes == ["a", "z"]


def test_extra_field_rejection() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        AIRecommendationResult.model_validate(
            {
                "executive_summary": "Summary",
                "overall_assessment": "Assessment",
                "evidence_coverage": {
                    "total_findings": 0,
                    "findings_considered": 0,
                    "findings_referenced": 0,
                    "coverage_percentage": 0.0,
                    "input_truncated": False,
                },
                "provider": "bedrock",
            }
        )


def test_unknown_dependency_rejected() -> None:
    with pytest.raises(ValidationError, match="dependencies"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[_recommendation("AI-REC-001", dependencies=["AI-REC-999"])],
            evidence_coverage=_coverage(total=0, considered=0, referenced=0),
        )


def test_duplicate_phase_numbers_rejected() -> None:
    with pytest.raises(ValidationError, match="phase numbers must be unique"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[_recommendation("AI-REC-001")],
            modernization_phases=[
                ModernizationPhase(
                    phase=1,
                    name="One",
                    objective="A",
                    recommendations=["AI-REC-001"],
                ),
                ModernizationPhase(
                    phase=1,
                    name="Also one",
                    objective="B",
                    recommendations=["AI-REC-001"],
                ),
            ],
            evidence_coverage=_coverage(total=0, considered=0, referenced=0),
        )


def test_invalid_ai_recommendation_id_format_rejected() -> None:
    with pytest.raises(ValidationError, match="AI-REC-NNN"):
        _recommendation("BestPractices.GuardLogStatement", related=["SEC001"])
    with pytest.raises(ValidationError, match="AI-REC-NNN"):
        _recommendation("DET-REC-001", related=["SEC001"])
    with pytest.raises(ValidationError, match="AI-REC-NNN"):
        _recommendation("REC-001", related=["SEC001"])
