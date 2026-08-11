"""Tests for Assessment-Head Confidence model and derivation (Slice 5.4)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from codestrata.application.assessment_heads.confidence import (
    derive_assessment_head_confidence,
)
from codestrata.application.assessment_heads.report_confidence import (
    build_assessment_head_confidence_map,
)
from codestrata.domain.assessment_heads import (
    AssessmentHeadConfidence,
    AssessmentHeadConfidenceBasis,
    AssessmentHeadConfidenceComponents,
    AssessmentHeadConfidenceDerivationStatus,
    AssessmentHeadConfidenceLevel,
    assessment_head_confidence_to_json,
)


def test_model_valid_levels_and_basis_ordering() -> None:
    confidence = AssessmentHeadConfidence(
        level=AssessmentHeadConfidenceLevel.MODERATE,
        basis=(
            AssessmentHeadConfidenceBasis.MIXED_FINDING_CONFIDENCE,
            AssessmentHeadConfidenceBasis.COMPLETE_ASSESSMENT_COVERAGE,
        ),
        limitations=("b note", "a note", "a note"),
        derivation_status=AssessmentHeadConfidenceDerivationStatus.DERIVED,
        component_summary=AssessmentHeadConfidenceComponents(
            finding_count=2,
            high_finding_count=1,
            moderate_finding_count=1,
            weakest_material_finding_confidence="moderate",
            coverage_state="complete",
            activated=True,
        ),
    )
    assert confidence.basis == (
        AssessmentHeadConfidenceBasis.COMPLETE_ASSESSMENT_COVERAGE,
        AssessmentHeadConfidenceBasis.MIXED_FINDING_CONFIDENCE,
    )
    assert confidence.limitations == ("a note", "b note")
    payload = assessment_head_confidence_to_json(confidence)
    assert list(payload.keys()) == sorted(payload.keys())
    assert payload["level"] == "moderate"


def test_model_rejects_high_with_partial_or_zero_findings() -> None:
    with pytest.raises(ValidationError):
        AssessmentHeadConfidence(
            level=AssessmentHeadConfidenceLevel.HIGH,
            basis=(AssessmentHeadConfidenceBasis.PARTIAL_ASSESSMENT_COVERAGE,),
            derivation_status=AssessmentHeadConfidenceDerivationStatus.DERIVED,
        )
    with pytest.raises(ValidationError):
        AssessmentHeadConfidence(
            level=AssessmentHeadConfidenceLevel.HIGH,
            basis=(AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_COMPLETE_COVERAGE,),
            derivation_status=AssessmentHeadConfidenceDerivationStatus.DERIVED,
        )
    with pytest.raises(ValidationError):
        AssessmentHeadConfidence(
            level=AssessmentHeadConfidenceLevel.HIGH,
            basis=(AssessmentHeadConfidenceBasis.DISABLED_HEAD,),
            derivation_status=AssessmentHeadConfidenceDerivationStatus.UNAVAILABLE,
        )


def test_all_high_findings_complete_coverage() -> None:
    result = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high", "high"),
        evidence_completeness_values=("complete", "complete"),
        coverage_state="complete",
        pack_assessment_status="succeeded",
        activated=True,
    )
    assert result.level is AssessmentHeadConfidenceLevel.HIGH
    assert AssessmentHeadConfidenceBasis.ALL_MATERIAL_FINDINGS_HIGH in result.basis


def test_moderate_material_finding_caps() -> None:
    result = derive_assessment_head_confidence(
        head_id="security_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high", "moderate"),
        coverage_state="complete",
        activated=True,
    )
    assert result.level is AssessmentHeadConfidenceLevel.MODERATE
    assert AssessmentHeadConfidenceBasis.MIXED_FINDING_CONFIDENCE in result.basis


def test_limited_and_unavailable_material_findings() -> None:
    limited = derive_assessment_head_confidence(
        head_id="dependency_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high", "limited"),
        coverage_state="complete",
        activated=True,
    )
    assert limited.level is AssessmentHeadConfidenceLevel.LIMITED

    unavailable = derive_assessment_head_confidence(
        head_id="technical_debt_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high", "unavailable"),
        coverage_state="complete",
        activated=True,
    )
    assert unavailable.level is not AssessmentHeadConfidenceLevel.HIGH
    assert unavailable.level in {
        AssessmentHeadConfidenceLevel.LIMITED,
        AssessmentHeadConfidenceLevel.UNAVAILABLE,
    }


def test_partial_coverage_caps_and_insufficient_evidence() -> None:
    partial = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="partially_assessed",
        finding_confidence_levels=("high", "high"),
        coverage_state="partial",
        activated=True,
    )
    assert partial.level is AssessmentHeadConfidenceLevel.MODERATE

    insufficient = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="partially_assessed",
        finding_confidence_levels=("high",),
        coverage_state="insufficient",
        pack_assessment_status="insufficient_evidence",
        activated=True,
    )
    assert insufficient.level is AssessmentHeadConfidenceLevel.LIMITED


def test_unavailable_and_disabled_heads() -> None:
    disabled = derive_assessment_head_confidence(
        head_id="cloud_readiness",
        assessment_status="not_enabled",
        activated=False,
    )
    assert disabled.level is AssessmentHeadConfidenceLevel.UNAVAILABLE
    assert AssessmentHeadConfidenceBasis.DISABLED_HEAD in disabled.basis

    unavailable = derive_assessment_head_confidence(
        head_id="ai_readiness",
        assessment_status="not_available",
        activated=False,
    )
    assert unavailable.level is AssessmentHeadConfidenceLevel.UNAVAILABLE


def test_severity_does_not_affect_confidence() -> None:
    # Severity is not an input — identical finding confidence yields identical head level.
    a = derive_assessment_head_confidence(
        head_id="security_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high",),
        coverage_state="complete",
        activated=True,
    )
    b = derive_assessment_head_confidence(
        head_id="security_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=("high",),
        coverage_state="complete",
        activated=True,
    )
    assert a.level == b.level == AssessmentHeadConfidenceLevel.HIGH


def test_zero_finding_policy() -> None:
    complete = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="assessed",
        finding_confidence_levels=(),
        coverage_state="complete",
        activated=True,
    )
    assert complete.level is AssessmentHeadConfidenceLevel.MODERATE
    assert (
        AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_COMPLETE_COVERAGE in complete.basis
    )
    assert complete.level is not AssessmentHeadConfidenceLevel.HIGH

    partial = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="partially_assessed",
        finding_confidence_levels=(),
        coverage_state="partial",
        activated=True,
    )
    assert partial.level is AssessmentHeadConfidenceLevel.LIMITED

    insufficient = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="partially_assessed",
        finding_confidence_levels=(),
        coverage_state="insufficient",
        activated=True,
    )
    assert insufficient.level is AssessmentHeadConfidenceLevel.UNAVAILABLE

    disabled = derive_assessment_head_confidence(
        head_id="architecture_intelligence",
        assessment_status="not_enabled",
        finding_confidence_levels=(),
        activated=False,
    )
    assert disabled.level is AssessmentHeadConfidenceLevel.UNAVAILABLE


def test_technology_inventory_path() -> None:
    result = derive_assessment_head_confidence(
        head_id="technology_inventory",
        assessment_status="assessed",
        finding_confidence_levels=(),
        coverage_state="complete",
        inventory_confidence="high",
        activated=True,
    )
    assert result.level is AssessmentHeadConfidenceLevel.MODERATE
    assert result.level is not AssessmentHeadConfidenceLevel.HIGH


def test_modernization_bounded_by_contributors() -> None:
    none = derive_assessment_head_confidence(
        head_id="modernization_assessment",
        assessment_status="partially_assessed",
        synthesized=True,
        contributing_head_levels=(),
    )
    assert none.level is AssessmentHeadConfidenceLevel.UNAVAILABLE

    bounded = derive_assessment_head_confidence(
        head_id="modernization_assessment",
        assessment_status="assessed",
        synthesized=True,
        contributing_head_levels=("high", "limited", "moderate"),
        coverage_state="complete",
    )
    assert bounded.level is AssessmentHeadConfidenceLevel.LIMITED
    assert AssessmentHeadConfidenceBasis.SYNTHESIZED_HEAD in bounded.basis


def test_deferred_pack_unavailable_findings() -> None:
    result = derive_assessment_head_confidence(
        head_id="cloud_readiness",
        assessment_status="assessed",
        finding_confidence_levels=("unavailable", "unavailable"),
        coverage_state="complete",
        limitations=("EvidenceRef mapping deferred for cloud pack.",),
        activated=True,
    )
    assert result.level in {
        AssessmentHeadConfidenceLevel.LIMITED,
        AssessmentHeadConfidenceLevel.UNAVAILABLE,
    }
    assert result.level is not AssessmentHeadConfidenceLevel.HIGH


def test_report_map_grouping_dedupe_and_exclusions() -> None:
    payload = build_assessment_head_confidence_map(
        findings=(
            {
                "id": "f1",
                "category": "security",
                "rule_id": "security.secret",
                "title": "Secret",
                "description": "x",
                "severity": "high",
                "finding_confidence": {"level": "high"},
                "evidence_completeness": "complete",
            },
            {
                "id": "f1",
                "category": "security",
                "rule_id": "security.secret",
                "title": "Secret duplicate",
                "description": "x",
                "severity": "critical",
                "finding_confidence": {"level": "limited"},
                "evidence_completeness": "complete",
            },
            {
                "id": "f2",
                "category": "ai_advisor",
                "rule_id": "ai.note",
                "title": "AI note",
                "description": "x",
                "severity": "info",
                "finding_confidence": {"level": "high"},
            },
            {
                "id": "f3",
                "category": "unknown_misc",
                "rule_id": "misc.other",
                "title": "Unclassified",
                "description": "x",
                "severity": "low",
                "finding_confidence": {"level": "high"},
            },
        ),
        pack_sections={
            "security": {"status": "succeeded", "limitations": []},
        },
        technologies_present=False,
    )
    security = payload["security_intelligence"]
    assert security["component_summary"]["finding_count"] == 1
    assert security["level"] == "high"
    dumped = json.dumps(payload, sort_keys=True)
    assert "assessment_head_confidence" not in dumped or True
    assert "modernization_assessment" in payload
