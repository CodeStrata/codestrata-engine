"""Additional AI recommendation consolidation and coverage contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRecommendationEvidence,
    LLMRepositoryContext,
    LLMSectionTruncation,
)
from codestrata.ai.recommendations import (
    AIRecommendation,
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
    AIRecommendationResult,
    AIRecommendationValidationError,
    EvidenceCoverage,
    ModernizationPhase,
    compute_evidence_coverage,
    validate_recommendation_result,
)


def _finding(rule_id: str, *, severity: str = "medium") -> LLMFindingEvidence:
    return LLMFindingEvidence(
        rule_id=rule_id,
        finding_id=f"finding:{rule_id}",
        title=f"Finding {rule_id}",
        category="quality",
        severity=severity,
        summary=f"Summary {rule_id}",
        evidence_truncation=LLMSectionTruncation(
            truncated=False, original_count=1, included_count=1
        ),
    )


def _context(
    *rule_ids: str,
    deterministic_ids: list[str] | None = None,
) -> LLMAnalysisContext:
    findings = [_finding(rule_id) for rule_id in rule_ids]
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(name="sample", source_type="local", file_count=10),
        metrics=LLMMetricsContext(
            finding_count=len(findings),
            technology_count=1,
            recommendation_count=len(deterministic_ids or []),
        ),
        findings=findings,
        findings_truncation=LLMSectionTruncation(
            truncated=False,
            original_count=len(findings),
            included_count=len(findings),
        ),
        deterministic_recommendations=[
            LLMRecommendationEvidence(
                recommendation_id=item_id,
                title=f"Deterministic {item_id}",
                priority="medium",
                category="quality",
                related_finding_ids=[rule_ids[0]] if rule_ids else [],
                summary="Deterministic remediation",
            )
            for item_id in (deterministic_ids or [])
        ],
    )


def _recommendation(
    recommendation_id: str,
    *,
    related: list[str],
    deterministic: list[str] | None = None,
) -> AIRecommendation:
    return AIRecommendation(
        recommendation_id=recommendation_id,
        title=f"Consolidate {recommendation_id}",
        description="Outcome-oriented modernization initiative",
        rationale="Grounded in multiple related findings",
        priority=AIRecommendationPriority.MEDIUM,
        effort=AIRecommendationEffort.MEDIUM,
        impact=AIRecommendationImpact.MEDIUM,
        confidence=AIRecommendationConfidence.MEDIUM,
        related_finding_ids=related,
        related_deterministic_recommendation_ids=deterministic or [],
        suggested_actions=["Implement consolidated remediation"],
    )


def _coverage(*, total: int, considered: int, referenced: int) -> EvidenceCoverage:
    percentage = 0.0 if considered == 0 else round(100.0 * referenced / considered, 2)
    return EvidenceCoverage(
        total_findings=total,
        findings_considered=considered,
        findings_referenced=referenced,
        coverage_percentage=percentage,
        input_truncated=False,
    )


def _result_with_count(count: int, context: LLMAnalysisContext) -> AIRecommendationResult:
    recommendations = [
        _recommendation(
            f"AI-REC-{index:03d}",
            related=[context.findings[index % len(context.findings)].rule_id],
        )
        for index in range(1, count + 1)
    ]
    midpoint = max(1, count // 2)
    phases = [
        ModernizationPhase(
            phase=1,
            name="Stabilize",
            objective="Reduce immediate risk",
            recommendations=[item.recommendation_id for item in recommendations[:midpoint]],
            expected_outcomes=["Safer baseline"],
        ),
        ModernizationPhase(
            phase=2,
            name="Standardize",
            objective="Improve delivery readiness",
            recommendations=[item.recommendation_id for item in recommendations[midpoint:]],
            expected_outcomes=["Consistent practices"],
        ),
    ]
    # Fabricated coverage values that validation should recompute.
    return AIRecommendationResult(
        executive_summary="Repository-specific strengths and gaps.",
        overall_assessment="Targeted hardening is warranted.",
        key_risks=["Reliability"],
        recommendations=recommendations,
        modernization_phases=phases,
        evidence_coverage=_coverage(total=len(context.findings), considered=1, referenced=0),
        limitations=["No runtime telemetry."],
    )


def test_five_synthesized_recommendations_accepted() -> None:
    context = _context(*[f"F{i:03d}" for i in range(1, 9)])
    validated = validate_recommendation_result(_result_with_count(5, context), context)
    assert len(validated.recommendations) == 5
    assert [item.recommendation_id for item in validated.recommendations] == [
        f"AI-REC-{index:03d}" for index in range(1, 6)
    ]


def test_eight_synthesized_recommendations_accepted() -> None:
    context = _context(*[f"F{i:03d}" for i in range(1, 9)])
    validated = validate_recommendation_result(_result_with_count(8, context), context)
    assert len(validated.recommendations) == 8


def test_nine_recommendations_rejected_for_evidence_rich_context() -> None:
    context = _context(*[f"F{i:03d}" for i in range(1, 9)])
    with pytest.raises(AIRecommendationValidationError, match="between 5 and 8"):
        validate_recommendation_result(_result_with_count(9, context), context)


def test_ai_recommendation_references_multiple_findings_and_deterministic_ids() -> None:
    context = _context("F001", "F002", "F003", deterministic_ids=["DET-REC-001", "DET-REC-002"])
    result = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        recommendations=[
            _recommendation(
                "AI-REC-001",
                related=["F001", "F002", "F003"],
                deterministic=["DET-REC-001", "DET-REC-002"],
            )
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Consolidate reliability work",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Fewer failure modes"],
            )
        ],
        evidence_coverage=_coverage(total=3, considered=3, referenced=1),
        limitations=["Source-only assessment."],
    )
    validated = validate_recommendation_result(result, context)
    assert validated.recommendations[0].related_finding_ids == ["F001", "F002", "F003"]
    assert validated.recommendations[0].related_deterministic_recommendation_ids == [
        "DET-REC-001",
        "DET-REC-002",
    ]
    assert validated.evidence_coverage.findings_referenced == 3
    assert validated.evidence_coverage.coverage_percentage == 100.0


def test_deterministic_id_in_related_finding_ids_rejected() -> None:
    context = _context("F001", deterministic_ids=["DET-REC-001"])
    result = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        recommendations=[
            _recommendation("AI-REC-001", related=["DET-REC-001"]),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Objective",
                recommendations=["AI-REC-001"],
            )
        ],
        evidence_coverage=_coverage(total=1, considered=1, referenced=1),
    )
    with pytest.raises(
        AIRecommendationValidationError,
        match="related_deterministic_recommendation_ids",
    ):
        validate_recommendation_result(result, context)


def test_empty_roadmap_phase_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[_recommendation("AI-REC-001", related=["F001"])],
            modernization_phases=[
                ModernizationPhase(
                    phase=1,
                    name="Empty",
                    objective="None",
                    recommendations=[],
                )
            ],
            evidence_coverage=_coverage(total=1, considered=1, referenced=1),
        )


def test_recommendation_omitted_from_roadmap_rejected() -> None:
    with pytest.raises(ValidationError, match="omit recommendation IDs"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[
                _recommendation("AI-REC-001", related=["F001"]),
                _recommendation("AI-REC-002", related=["F002"]),
            ],
            modernization_phases=[
                ModernizationPhase(
                    phase=1,
                    name="Stabilize",
                    objective="Partial",
                    recommendations=["AI-REC-001"],
                )
            ],
            evidence_coverage=_coverage(total=2, considered=2, referenced=2),
        )


def test_unknown_roadmap_ai_id_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown recommendation IDs"):
        AIRecommendationResult(
            executive_summary="Summary",
            overall_assessment="Assessment",
            recommendations=[_recommendation("AI-REC-001", related=["F001"])],
            modernization_phases=[
                ModernizationPhase(
                    phase=1,
                    name="Stabilize",
                    objective="Objective",
                    recommendations=["AI-REC-001", "AI-REC-009"],
                )
            ],
            evidence_coverage=_coverage(total=1, considered=1, referenced=1),
        )


def test_evidence_coverage_recomputed_from_unique_related_finding_ids() -> None:
    context = _context("F001", "F002", "F003", "F004")
    result = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        recommendations=[
            _recommendation("AI-REC-001", related=["F001", "F002"]),
            _recommendation("AI-REC-002", related=["F002", "F003"]),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="One",
                recommendations=["AI-REC-001"],
            ),
            ModernizationPhase(
                phase=2,
                name="Standardize",
                objective="Two",
                recommendations=["AI-REC-002"],
            ),
        ],
        evidence_coverage=_coverage(total=4, considered=1, referenced=0),
    )
    computed = compute_evidence_coverage(result, context)
    assert computed.findings_referenced == 3
    assert computed.findings_considered == 4
    assert computed.coverage_percentage == 75.0
    validated = validate_recommendation_result(result, context)
    assert validated.evidence_coverage == computed


def test_incorrect_model_coverage_arithmetic_is_ignored_and_overwritten() -> None:
    context = _context("F001", "F002", "F003")
    # Mirrors the live Nova failure shape: inconsistent percentage, wrong counts.
    result = AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        recommendations=[
            _recommendation("AI-REC-001", related=["F001", "F002", "F001"]),
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Consolidate reliability",
                recommendations=["AI-REC-001"],
            )
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=34,
            findings_considered=15,
            findings_referenced=15,
            coverage_percentage=44.12,
            input_truncated=True,
        ),
    )
    validated = validate_recommendation_result(result, context)
    assert validated.evidence_coverage.total_findings == 3
    assert validated.evidence_coverage.findings_considered == 3
    assert validated.evidence_coverage.findings_referenced == 2
    assert validated.evidence_coverage.coverage_percentage == 66.67
    assert validated.evidence_coverage.input_truncated is False


def test_zero_findings_considered_coverage_is_safe() -> None:
    context = LLMAnalysisContext(
        repository=LLMRepositoryContext(name="empty", source_type="local", file_count=0),
        metrics=LLMMetricsContext(finding_count=0, technology_count=0),
        findings=[],
        findings_truncation=LLMSectionTruncation(
            truncated=False,
            original_count=0,
            included_count=0,
        ),
    )
    result = AIRecommendationResult(
        executive_summary="Minimal",
        overall_assessment="Minimal",
        evidence_coverage=EvidenceCoverage(
            total_findings=99,
            findings_considered=12,
            findings_referenced=4,
            coverage_percentage=10.0,
        ),
    )
    validated = validate_recommendation_result(result, context)
    assert validated.evidence_coverage.findings_considered == 0
    assert validated.evidence_coverage.findings_referenced == 0
    assert validated.evidence_coverage.coverage_percentage == 0.0


def test_parse_accepts_inconsistent_model_coverage_without_fallback() -> None:
    import json

    from codestrata.ai.providers.parsing import parse_recommendation_response

    context = _context("F001", "F002")
    payload = {
        "schema_version": "1.0.0",
        "executive_summary": "Summary",
        "overall_assessment": "Assessment",
        "key_risks": [],
        "recommendations": [
            {
                "recommendation_id": "AI-REC-001",
                "title": "Consolidate reliability",
                "description": "Outcome initiative",
                "rationale": "Grounded evidence",
                "priority": "medium",
                "effort": "medium",
                "impact": "medium",
                "confidence": "medium",
                "related_finding_ids": ["F001", "F002"],
                "related_deterministic_recommendation_ids": [],
                "suggested_actions": ["Act"],
                "dependencies": [],
            }
        ],
        "modernization_phases": [
            {
                "phase": 1,
                "name": "Stabilize",
                "objective": "Reduce risk",
                "recommendations": ["AI-REC-001"],
                "expected_outcomes": ["Safer baseline"],
            }
        ],
        "evidence_coverage": {
            "total_findings": 34,
            "findings_considered": 15,
            "findings_referenced": 15,
            "coverage_percentage": 44.12,
            "input_truncated": False,
        },
        "limitations": [],
    }
    parsed = parse_recommendation_response(json.dumps(payload), context)
    assert parsed.result.evidence_coverage.findings_considered == 2
    assert parsed.result.evidence_coverage.findings_referenced == 2
    assert parsed.result.evidence_coverage.coverage_percentage == 100.0


def test_aggregated_validation_issues_include_count_and_unknown_findings() -> None:
    context = _context(*[f"F{i:03d}" for i in range(1, 9)])
    result = _result_with_count(9, context)
    # Also inject an unknown finding reference on the first recommendation.
    first = result.recommendations[0]
    broken_first = first.model_copy(update={"related_finding_ids": ["MISSING"]})
    result = result.model_copy(
        update={"recommendations": [broken_first, *result.recommendations[1:]]}
    )
    with pytest.raises(AIRecommendationValidationError) as info:
        validate_recommendation_result(result, context)
    message = str(info.value)
    assert "between 5 and 8" in message
    assert "MISSING" in message
    assert len(info.value.issues) >= 2
