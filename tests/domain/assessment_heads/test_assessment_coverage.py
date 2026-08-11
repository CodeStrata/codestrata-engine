"""Tests for Assessment Coverage model and derivation (Slice 5.6)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from codestrata.application.assessment_heads.confidence import (
    derive_assessment_head_confidence,
)
from codestrata.application.assessment_heads.coverage import (
    build_assessment_coverage_map,
    coverage_summary_rows,
    derive_assessment_coverage,
)
from codestrata.domain.assessment_heads.assessment_coverage import (
    AreaClaimState,
    AreaEvaluationState,
    AreaSupportState,
    AssessmentAreaCoverage,
    AssessmentCoverage,
    AssessmentCoverageScope,
    AssessmentCoverageTotals,
    CoverageDerivationStatus,
    CoverageMetric,
    CoverageMetricId,
    CoverageStatus,
    assessment_coverage_to_json,
)


def test_model_rejects_invalid_totals_and_metrics() -> None:
    with pytest.raises(ValidationError):
        AssessmentCoverageTotals(
            applicable_area_count=1,
            evaluated_area_count=2,
        )
    with pytest.raises(ValidationError):
        CoverageMetric.build(
            metric_id=CoverageMetricId.AREA_COVERAGE,
            numerator=2,
            denominator=1,
        )
    unavailable = CoverageMetric.build(
        metric_id=CoverageMetricId.AREA_COVERAGE,
        numerator=0,
        denominator=0,
    )
    assert unavailable.availability.value == "unavailable"
    assert unavailable.ratio is None


def test_metric_ratio_reconciles() -> None:
    metric = CoverageMetric.build(
        metric_id=CoverageMetricId.CANDIDATE_PROCESSING,
        numerator=10,
        denominator=12,
    )
    assert metric.ratio == Decimal("0.8333")
    assert metric.availability.value == "available"


def test_not_claimed_excluded_from_denominator() -> None:
    coverage = derive_assessment_coverage(
        head_id="technical_debt_intelligence",
        pack_id="technical_debt",
        pack_status="succeeded",
        activated=True,
        pack_section={
            "status": "succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "debt_rule_coverage", "status": "measured"},
                    {"area_id": "complexity_coverage", "status": "measured"},
                    {"area_id": "duplication_coverage", "status": "unsupported"},
                ]
            },
            "execution_summary": {
                "technical_debt_rules_planned": 4,
                "rules_executed": 4,
            },
        },
    )
    assert coverage.totals.applicable_area_count >= 2
    duplication = next(
        item for item in coverage.areas if item.area_id == "duplication_coverage"
    )
    assert duplication.claim_state is AreaClaimState.NOT_CLAIMED
    assert duplication.evaluation_state is AreaEvaluationState.NOT_APPLICABLE
    area_metric = next(
        item for item in coverage.metrics if item.metric_id is CoverageMetricId.AREA_COVERAGE
    )
    assert area_metric.denominator == coverage.totals.applicable_area_count


def test_disabled_and_insufficient_distinct() -> None:
    disabled = derive_assessment_coverage(
        head_id="security_intelligence",
        pack_status="disabled",
        activated=False,
    )
    assert disabled.status is CoverageStatus.DISABLED

    insufficient = derive_assessment_coverage(
        head_id="security_intelligence",
        pack_status="insufficient_evidence",
        activated=True,
        pack_section={"status": "insufficient_evidence"},
    )
    assert insufficient.status is CoverageStatus.INSUFFICIENT_EVIDENCE


def test_findings_do_not_determine_coverage() -> None:
    with_findings = derive_assessment_coverage(
        head_id="architecture_intelligence",
        pack_status="succeeded",
        activated=True,
        pack_section={
            "status": "succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "extraction_coverage", "status": "measured"},
                    {"area_id": "classification_coverage", "status": "measured"},
                    {"area_id": "architecture_rules", "status": "measured"},
                ]
            },
            "finding_count": 0,
        },
    )
    many_findings = derive_assessment_coverage(
        head_id="architecture_intelligence",
        pack_status="succeeded",
        activated=True,
        pack_section={
            "status": "succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "extraction_coverage", "status": "measured"},
                    {"area_id": "classification_coverage", "status": "measured"},
                    {"area_id": "architecture_rules", "status": "measured"},
                ]
            },
            "finding_count": 99,
        },
    )
    assert with_findings.status == many_findings.status
    assert with_findings.totals.applicable_area_count == many_findings.totals.applicable_area_count


def test_candidate_and_rule_metrics() -> None:
    coverage = derive_assessment_coverage(
        head_id="security_intelligence",
        pack_status="partially_succeeded",
        activated=True,
        pack_section={
            "status": "partially_succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "security_capability_requested", "status": "measured"},
                    {"area_id": "security_rules_enabled", "status": "measured"},
                    {"area_id": "security_evidence_availability", "status": "partial"},
                ]
            },
            "execution_summary": {
                "security_rules_planned": 8,
                "rules_executed": 8,
            },
            "evidence_coverage": {
                "candidate_files_discovered": 12,
                "candidate_files_parsed": 10,
                "candidate_files_partially_parsed": 1,
                "candidate_files_malformed": 1,
            },
        },
    )
    assert coverage.status is CoverageStatus.PARTIAL
    ids = {item.metric_id for item in coverage.metrics}
    assert CoverageMetricId.CANDIDATE_PROCESSING in ids
    assert CoverageMetricId.RULE_EXECUTION in ids
    candidate = next(
        item
        for item in coverage.metrics
        if item.metric_id is CoverageMetricId.CANDIDATE_PROCESSING
    )
    assert candidate.numerator == 11
    assert candidate.denominator == 12


def test_modernization_bounded_by_contributors() -> None:
    security = derive_assessment_coverage(
        head_id="security_intelligence",
        pack_status="succeeded",
        activated=True,
        pack_section={
            "status": "succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "security_capability_requested", "status": "measured"},
                    {"area_id": "security_rules_enabled", "status": "measured"},
                    {"area_id": "security_evidence_availability", "status": "measured"},
                ]
            },
        },
    )
    dependency = derive_assessment_coverage(
        head_id="dependency_intelligence",
        pack_status="partially_succeeded",
        activated=True,
        pack_section={
            "status": "partially_succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "dependency_rule_coverage", "status": "partial"},
                    {"area_id": "dependency_evidence_coverage", "status": "measured"},
                ]
            },
        },
    )
    modernization = derive_assessment_coverage(
        head_id="modernization_assessment",
        pack_status="succeeded",
        activated=True,
        contributing_head_coverage=(security, dependency),
        pack_section={"initiatives_total": 3},
    )
    assert modernization.status is CoverageStatus.PARTIAL
    assert "cannot exceed contributing head coverage" in " ".join(
        modernization.limitations
    ).lower()


def test_coverage_map_and_json_stable() -> None:
    payload = build_assessment_coverage_map(
        pack_sections={
            "security": {
                "status": "succeeded",
                "coverage": {
                    "areas": [
                        {"area_id": "security_capability_requested", "status": "measured"},
                        {"area_id": "security_rules_enabled", "status": "measured"},
                        {
                            "area_id": "security_evidence_availability",
                            "status": "measured",
                        },
                    ]
                },
            }
        },
        technologies_present=True,
        activation={"assessed_packs": ("security",), "not_assessed_packs": ()},
    )
    assert "security_intelligence" in payload
    assert "technology_inventory" in payload
    assert list(payload.keys()) == sorted(payload.keys())
    dumped = assessment_coverage_to_json(
        AssessmentCoverage.model_validate(payload["security_intelligence"])
    )
    assert dumped["status"] in {"complete", "partial", "insufficient_evidence"}


def test_confidence_consumes_canonical_coverage() -> None:
    coverage = derive_assessment_coverage(
        head_id="architecture_intelligence",
        pack_status="partially_succeeded",
        activated=True,
        pack_section={
            "status": "partially_succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "extraction_coverage", "status": "measured"},
                    {"area_id": "classification_coverage", "status": "partial"},
                ]
            },
        },
    )
    confidence = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high", "high"),
        coverage_state="complete",  # free-form guess would be complete
        assessment_coverage=coverage,  # canonical partial must win
        activated=True,
    )
    assert confidence.level.value != "high"
    assert confidence.component_summary.coverage_state == "partial"


def test_zero_findings_policy_unchanged_with_complete_coverage() -> None:
    coverage = derive_assessment_coverage(
        head_id="architecture_intelligence",
        pack_status="succeeded",
        activated=True,
        pack_section={
            "status": "succeeded",
            "coverage": {
                "areas": [
                    {"area_id": "extraction_coverage", "status": "measured"},
                    {"area_id": "classification_coverage", "status": "measured"},
                    {"area_id": "architecture_rules", "status": "measured"},
                ]
            },
        },
    )
    confidence = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=(),
        assessment_coverage=coverage,
        activated=True,
    )
    assert confidence.level.value == "moderate"
    rows = coverage_summary_rows(coverage)
    assert any("supported areas evaluated" in row[0].lower() for row in rows)
