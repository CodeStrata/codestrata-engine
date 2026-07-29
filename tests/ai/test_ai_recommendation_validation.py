"""Tests for AI recommendation evidence validation."""

from __future__ import annotations

import pytest

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMEvidenceLocation,
    LLMFindingEvidence,
    LLMMetricsContext,
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
    EvidenceCoverage,
    ModernizationPhase,
)
from codestrata.ai.recommendations.validation import (
    AIRecommendationValidationError,
    validate_recommendation_result,
)


def _context(*, findings: list[LLMFindingEvidence] | None = None) -> LLMAnalysisContext:
    items = findings or [
        LLMFindingEvidence(
            finding_id="f-sec",
            rule_id="SEC001",
            group_id=None,
            title="Secret exposure",
            category="security",
            severity="critical",
            summary="Secret in source",
            evidence=[LLMEvidenceLocation(path="src/App.java", line=12)],
            evidence_truncation=LLMSectionTruncation(
                truncated=False, original_count=1, included_count=1
            ),
        ),
        LLMFindingEvidence(
            finding_id="pmd:BestPractices.GuardLogStatement",
            rule_id="BestPractices.GuardLogStatement",
            group_id="pmd:BestPractices.GuardLogStatement",
            title="Unguarded log",
            category="quality",
            severity="medium",
            summary="Log without guard",
            customer_visibility="primary",
            evidence=[LLMEvidenceLocation(path="src/Service.java", line=40)],
            evidence_truncation=LLMSectionTruncation(
                truncated=False, original_count=1, included_count=1
            ),
        ),
    ]
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample-app",
            source_type="local",
            file_count=2,
        ),
        metrics=LLMMetricsContext(
            finding_count=len(items),
            technology_count=1,
            recommendation_count=0,
        ),
        findings=items,
        findings_truncation=LLMSectionTruncation(
            truncated=False,
            original_count=len(items),
            included_count=len(items),
        ),
    )


def _result(
    *,
    related: list[str] | None = None,
    priority: AIRecommendationPriority = AIRecommendationPriority.HIGH,
    description: str = "Harden secrets handling",
    actions: list[str] | None = None,
) -> AIRecommendationResult:
    return AIRecommendationResult(
        executive_summary="Summary",
        overall_assessment="Assessment",
        key_risks=["Secret exposure"],
        recommendations=[
            AIRecommendation(
                recommendation_id="AI-REC-001",
                title="Rotate secrets",
                description=description,
                rationale="Grounded in SEC001",
                priority=priority,
                effort=AIRecommendationEffort.MEDIUM,
                impact=AIRecommendationImpact.HIGH,
                confidence=AIRecommendationConfidence.MEDIUM,
                related_finding_ids=related if related is not None else ["SEC001"],
                suggested_actions=actions or ["Rotate credentials"],
                dependencies=[],
            )
        ],
        modernization_phases=[
            ModernizationPhase(
                phase=1,
                name="Stabilize",
                objective="Reduce risk",
                recommendations=["AI-REC-001"],
                expected_outcomes=["Safer baseline"],
            )
        ],
        evidence_coverage=EvidenceCoverage(
            total_findings=2,
            findings_considered=2,
            findings_referenced=1,
            coverage_percentage=50.0,
        ),
        limitations=["No runtime data"],
    )


def test_valid_finding_and_group_references_accepted() -> None:
    validate_recommendation_result(
        _result(related=["SEC001", "pmd:BestPractices.GuardLogStatement"]),
        _context(),
    )


def test_unknown_references_rejected() -> None:
    with pytest.raises(AIRecommendationValidationError, match="not present"):
        validate_recommendation_result(_result(related=["UNKNOWN-ID"]), _context())


def test_empty_evidence_rejected() -> None:
    with pytest.raises(AIRecommendationValidationError, match="ungrounded"):
        validate_recommendation_result(_result(related=[]), _context())


def test_unsupported_severity_escalation_rejected() -> None:
    low_only = _context(
        findings=[
            LLMFindingEvidence(
                finding_id="f-low",
                rule_id="STYLE001",
                title="Style",
                category="quality",
                severity="low",
                summary="Style issue",
                evidence=[LLMEvidenceLocation(path="src/App.java")],
                evidence_truncation=LLMSectionTruncation(
                    truncated=False, original_count=1, included_count=1
                ),
            )
        ]
    )
    with pytest.raises(AIRecommendationValidationError, match="escalates severity"):
        validate_recommendation_result(
            AIRecommendationResult(
                executive_summary="Summary",
                overall_assessment="Assessment",
                key_risks=[],
                recommendations=[
                    AIRecommendation(
                        recommendation_id="AI-REC-001",
                        title="Critical style rewrite",
                        description="Escalate",
                        rationale="Unsupported",
                        priority=AIRecommendationPriority.CRITICAL,
                        effort=AIRecommendationEffort.SMALL,
                        impact=AIRecommendationImpact.HIGH,
                        confidence=AIRecommendationConfidence.LOW,
                        related_finding_ids=["STYLE001"],
                        suggested_actions=["Rewrite"],
                    )
                ],
                modernization_phases=[],
                evidence_coverage=EvidenceCoverage(
                    total_findings=1,
                    findings_considered=1,
                    findings_referenced=1,
                    coverage_percentage=100.0,
                ),
            ),
            low_only,
        )


def test_invalid_paths_rejected() -> None:
    with pytest.raises(AIRecommendationValidationError, match="absolute path|not present"):
        validate_recommendation_result(
            _result(actions=["Edit /Users/secret/App.java immediately"]),
            _context(),
        )


def test_invented_relative_path_rejected() -> None:
    with pytest.raises(AIRecommendationValidationError, match="not present"):
        validate_recommendation_result(
            _result(actions=["Fix invented/path/DoesNotExist.java"]),
            _context(),
        )
