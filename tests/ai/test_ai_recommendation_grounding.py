"""Tests for AI recommendation grounding and deterministic ID normalization."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.ai.agents.models import (
    AgentExecutionStatus,
    AgentExecutionTrace,
    ModernizationAssessmentResult,
)
from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRecommendationEvidence,
    LLMRepositoryContext,
    LLMSectionTruncation,
)
from codestrata.ai.providers.models import ModelInvocationMetadata, ModelUsage
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
    normalize_related_deterministic_recommendation_ids,
    validate_recommendation_result,
    validate_recommendation_result_outcome,
)
from codestrata.reporting.ai_status import stages_for_status
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.modernization_html import ModernizationHTMLReportRenderer
from codestrata.reporting.modernization_models import (
    AIAttemptInfo,
    AIExecutionStatus,
    AssessmentMode,
    ModernizationReportInput,
)
from tests.reporting.test_assessment_json import _analysis_result


def _finding(rule_id: str, *, severity: str = "medium") -> LLMFindingEvidence:
    return LLMFindingEvidence(
        rule_id=rule_id,
        finding_id=f"finding:{rule_id}",
        group_id=f"pmd-group-{rule_id}",
        title=f"Finding {rule_id}",
        category="quality",
        severity=severity,
        summary=f"Summary {rule_id}",
        evidence_truncation=LLMSectionTruncation(
            truncated=False, original_count=1, included_count=1
        ),
    )


def _det(recommendation_id: str, *, related: list[str] | None = None) -> LLMRecommendationEvidence:
    return LLMRecommendationEvidence(
        recommendation_id=recommendation_id,
        title=f"Deterministic {recommendation_id}",
        priority="medium",
        category="quality",
        related_finding_ids=related or [],
        summary="Deterministic remediation grounded in repository facts or findings",
    )


def _context(
    *rule_ids: str,
    deterministic_ids: list[str] | None = None,
) -> LLMAnalysisContext:
    findings = [_finding(rule_id) for rule_id in rule_ids]
    det_ids = deterministic_ids or []
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(name="sample", source_type="local", file_count=10),
        metrics=LLMMetricsContext(
            finding_count=len(findings),
            technology_count=1,
            recommendation_count=len(det_ids),
        ),
        findings=findings,
        findings_truncation=LLMSectionTruncation(
            truncated=False,
            original_count=len(findings),
            included_count=len(findings),
        ),
        deterministic_recommendations=[
            _det(item_id, related=[rule_ids[0]] if rule_ids else []) for item_id in det_ids
        ],
    )


def _recommendation(
    recommendation_id: str = "AI-REC-001",
    *,
    related: list[str] | None = None,
    deterministic: list[str] | None = None,
    priority: AIRecommendationPriority = AIRecommendationPriority.MEDIUM,
) -> AIRecommendation:
    return AIRecommendation(
        recommendation_id=recommendation_id,
        title=f"Consolidate {recommendation_id}",
        description="Outcome-oriented modernization initiative",
        rationale="Grounded in supplied evidence",
        priority=priority,
        effort=AIRecommendationEffort.MEDIUM,
        impact=AIRecommendationImpact.MEDIUM,
        confidence=AIRecommendationConfidence.MEDIUM,
        related_finding_ids=related or [],
        related_deterministic_recommendation_ids=deterministic or [],
        suggested_actions=["Implement consolidated remediation"],
    )


def _result(
    *recommendations: AIRecommendation,
    considered: int | None = None,
) -> AIRecommendationResult:
    items = list(recommendations) or [_recommendation(related=["F001"])]
    midpoint = max(1, len(items) // 2)
    phases = [
        ModernizationPhase(
            phase=1,
            name="Stabilize",
            objective="Reduce immediate risk",
            recommendations=[item.recommendation_id for item in items[:midpoint]],
            expected_outcomes=["Safer baseline"],
        )
    ]
    if len(items) > midpoint:
        phases.append(
            ModernizationPhase(
                phase=2,
                name="Standardize",
                objective="Improve delivery readiness",
                recommendations=[item.recommendation_id for item in items[midpoint:]],
                expected_outcomes=["Consistent practices"],
            )
        )
    finding_count = considered if considered is not None else 1
    return AIRecommendationResult(
        executive_summary="Repository-specific strengths and gaps.",
        overall_assessment="Targeted hardening is warranted.",
        key_risks=["Reliability"],
        recommendations=items,
        modernization_phases=phases,
        evidence_coverage=EvidenceCoverage(
            total_findings=finding_count,
            findings_considered=finding_count,
            findings_referenced=0,
            coverage_percentage=0.0,
        ),
        limitations=["No runtime telemetry."],
    )


def test_valid_finding_ids_without_deterministic_ids_accepted() -> None:
    context = _context("F001", "F002")
    validated = validate_recommendation_result(
        _result(_recommendation(related=["F001", "F002"])),
        context,
    )
    assert validated.recommendations[0].related_finding_ids == ["F001", "F002"]
    assert validated.recommendations[0].related_deterministic_recommendation_ids == []


def test_valid_deterministic_id_without_finding_ids_accepted() -> None:
    context = _context(deterministic_ids=["DET-REC-001"])
    validated = validate_recommendation_result(
        _result(_recommendation(related=[], deterministic=["DET-REC-001"])),
        context,
    )
    assert validated.recommendations[0].related_finding_ids == []
    assert validated.recommendations[0].related_deterministic_recommendation_ids == ["DET-REC-001"]


def test_cloud_repository_fact_recommendation_accepted_without_findings() -> None:
    context = _context(deterministic_ids=["REC.CLOUD.003"])
    validated = validate_recommendation_result(
        _result(
            _recommendation(
                "AI-REC-001",
                related=[],
                deterministic=["REC.CLOUD.003"],
            )
        ),
        context,
    )
    assert validated.recommendations[0].related_finding_ids == []
    assert validated.recommendations[0].related_deterministic_recommendation_ids == [
        "REC.CLOUD.003"
    ]
    assert validated.evidence_coverage.findings_referenced == 0


def test_neither_evidence_source_rejected() -> None:
    context = _context("F001", deterministic_ids=["DET-REC-001"])
    with pytest.raises(AIRecommendationValidationError, match="ungrounded"):
        validate_recommendation_result(
            _result(_recommendation(related=[], deterministic=[])),
            context,
        )


def test_unknown_finding_id_rejected() -> None:
    context = _context("F001", deterministic_ids=["DET-REC-001"])
    with pytest.raises(AIRecommendationValidationError, match="not present"):
        validate_recommendation_result(
            _result(_recommendation(related=["UNKNOWN-FINDING"])),
            context,
        )


def test_unknown_deterministic_id_removed_when_valid_findings_remain(
    caplog: pytest.LogCaptureFixture,
) -> None:
    context = _context(
        "F001",
        deterministic_ids=["REC.PMD.JAVA.ERRORPRONE.PROPERLOGGER"],
    )
    with caplog.at_level(logging.DEBUG, logger="codestrata.ai.recommendations.validation"):
        outcome = validate_recommendation_result_outcome(
            _result(
                _recommendation(
                    related=["F001"],
                    deterministic=[
                        "REC.PMD.JAVA.ERRORPRONE.PROPERLOGGER",
                        "REC.PMD.JAVA.BESTPRACTICES.SYSTEMPRINTLN",
                    ],
                )
            ),
            context,
        )
    assert outcome.result.recommendations[0].related_deterministic_recommendation_ids == [
        "REC.PMD.JAVA.ERRORPRONE.PROPERLOGGER"
    ]
    assert outcome.removed_unknown_deterministic_recommendation_ids == (
        "REC.PMD.JAVA.BESTPRACTICES.SYSTEMPRINTLN",
    )
    assert "removed_unknown_deterministic_recommendation_ids" in caplog.text


def test_mix_of_valid_and_invalid_deterministic_ids_preserves_valid_only() -> None:
    available = {"DET-A", "DET-C"}
    kept, removed = normalize_related_deterministic_recommendation_ids(
        ["DET-A", "DET-B", "DET-C", "DET-D"],
        available=available,
    )
    assert kept == ["DET-A", "DET-C"]
    assert removed == ["DET-B", "DET-D"]


def test_all_invalid_deterministic_ids_removed_but_valid_finding_accepted() -> None:
    context = _context("F001", deterministic_ids=["DET-REC-001"])
    outcome = validate_recommendation_result_outcome(
        _result(
            _recommendation(
                related=["F001"],
                deterministic=["REC.INVENTED.FROM.PMD"],
            )
        ),
        context,
    )
    assert outcome.result.recommendations[0].related_finding_ids == ["F001"]
    assert outcome.result.recommendations[0].related_deterministic_recommendation_ids == []
    assert outcome.removed_unknown_deterministic_recommendation_ids == ("REC.INVENTED.FROM.PMD",)


def test_all_invalid_deterministic_ids_removed_and_no_findings_rejected() -> None:
    context = _context(deterministic_ids=["DET-REC-001"])
    with pytest.raises(AIRecommendationValidationError, match="ungrounded"):
        validate_recommendation_result(
            _result(
                _recommendation(
                    related=[],
                    deterministic=["REC.INVENTED.FROM.PMD"],
                )
            ),
            context,
        )


def test_duplicate_deterministic_ids_normalized_and_order_preserved() -> None:
    kept, removed = normalize_related_deterministic_recommendation_ids(
        ["DET-B", "DET-A", "DET-B", "DET-UNKNOWN", "DET-A"],
        available={"DET-A", "DET-B"},
    )
    assert kept == ["DET-B", "DET-A"]
    assert removed == ["DET-UNKNOWN"]

    context = _context(deterministic_ids=["DET-B", "DET-A"])
    validated = validate_recommendation_result(
        _result(
            _recommendation(
                related=[],
                deterministic=["DET-B", "DET-A", "DET-B"],
            )
        ),
        context,
    )
    assert validated.recommendations[0].related_deterministic_recommendation_ids == [
        "DET-B",
        "DET-A",
    ]


def test_live_style_ai_rec_003_and_005_accepted() -> None:
    context = _context(
        "ProperLogger",
        "SystemPrintln",
        deterministic_ids=[
            "REC.PMD.JAVA.ERRORPRONE.PROPERLOGGER",
            "REC.CLOUD.003",
        ],
    )
    result = _result(
        _recommendation(
            "AI-REC-001",
            related=["pmd-group-ProperLogger", "pmd-group-SystemPrintln"],
            deterministic=[
                "REC.PMD.JAVA.ERRORPRONE.PROPERLOGGER",
                "REC.PMD.JAVA.BESTPRACTICES.SYSTEMPRINTLN",
            ],
        ),
        _recommendation(
            "AI-REC-002",
            related=[],
            deterministic=["REC.CLOUD.003"],
        ),
        considered=2,
    )
    outcome = validate_recommendation_result_outcome(result, context)
    rec_logging, rec_cloud = outcome.result.recommendations
    assert rec_logging.related_finding_ids == [
        "pmd-group-ProperLogger",
        "pmd-group-SystemPrintln",
    ]
    assert rec_logging.related_deterministic_recommendation_ids == [
        "REC.PMD.JAVA.ERRORPRONE.PROPERLOGGER"
    ]
    assert rec_cloud.related_finding_ids == []
    assert rec_cloud.related_deterministic_recommendation_ids == ["REC.CLOUD.003"]
    assert outcome.removed_unknown_deterministic_recommendation_ids == (
        "REC.PMD.JAVA.BESTPRACTICES.SYSTEMPRINTLN",
    )
    assert outcome.result.evidence_coverage.findings_referenced == 2


def test_evidence_coverage_counts_finding_ids_only() -> None:
    context = _context("F001", "F002", deterministic_ids=["REC.CLOUD.003", "DET-REC-001"])
    validated = validate_recommendation_result(
        _result(
            _recommendation(
                "AI-REC-001",
                related=["F001"],
                deterministic=["DET-REC-001"],
            ),
            _recommendation(
                "AI-REC-002",
                related=[],
                deterministic=["REC.CLOUD.003"],
            ),
            considered=2,
        ),
        context,
    )
    assert validated.evidence_coverage.findings_referenced == 1
    assert validated.evidence_coverage.coverage_percentage == 50.0


def test_normalized_successful_response_status_and_html_have_no_warning(
    tmp_path: Path,
) -> None:
    context = _context("F001", deterministic_ids=["DET-REC-001"])
    # Align repository name with analysis_result fixture used by HTML rendering.
    context = context.model_copy(
        update={
            "repository": context.repository.model_copy(update={"name": "sample-app"}),
        }
    )
    outcome = validate_recommendation_result_outcome(
        _result(
            _recommendation(
                related=["F001"],
                deterministic=["DET-REC-001", "REC.INVENTED"],
            )
        ),
        context,
    )
    assert outcome.removed_unknown_deterministic_recommendation_ids == ("REC.INVENTED",)

    assessment = ModernizationAssessmentResult(
        recommendation_result=outcome.result,
        model_metadata=ModelInvocationMetadata(
            provider="fake",
            model_id="test-model",
            request_id="req-1",
            latency_ms=12.5,
            usage=ModelUsage(input_tokens=9, output_tokens=11, total_tokens=20),
            stop_reason="end_turn",
        ),
        trace=AgentExecutionTrace(
            trace_id="trace-1",
            started_at_utc=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            completed_at_utc=datetime(2026, 7, 21, 12, 1, tzinfo=UTC),
            total_latency_ms=1000.0,
            status=AgentExecutionStatus.COMPLETED,
            steps=(),
            tool_call_count=0,
            model_call_count=1,
            input_tokens=9,
            output_tokens=11,
            total_tokens=20,
        ),
        raw_model_response='{"ok":true}',
    )
    report_input = ModernizationReportInput(
        analysis_result=_analysis_result(tmp_path),
        assessment_mode=AssessmentMode.AI_ENHANCED,
        analysis_context=context,
        assessment_result=assessment,
        ai_status=AIExecutionStatus.SUCCEEDED,
        ai_attempt=AIAttemptInfo(
            provider="fake",
            model_id="test-model",
            input_tokens=9,
            output_tokens=11,
            total_tokens=20,
            latency_ms=12.5,
            stages_completed=stages_for_status(AIExecutionStatus.SUCCEEDED),
        ),
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
    )
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    assert document["assessment"]["ai"]["status"] == "succeeded"
    assert document["assessment"]["ai"]["result_included"] is True
    assert "removed_unknown_deterministic_recommendation_ids" not in html
    assert "normalization" not in html.lower()
    assert "REC.INVENTED" not in html
