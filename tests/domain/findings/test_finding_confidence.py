"""Tests for Finding Confidence model and derivation (Slice 5.3)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from codestrata.application.findings.finding_confidence import (
    derive_finding_confidence,
    match_evidence_confidence_support,
)
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.security.helpers import match as security_match
from codestrata.application.traceability.merge import merge_finding_traceability
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingConfidence,
    FindingConfidenceBasis,
    FindingConfidenceDerivationStatus,
    FindingConfidenceLevel,
    FindingSeverity,
    finding_confidence_to_json,
)
from codestrata.domain.rules.enums import (
    MatchEvidenceConfidence,
    RuleCategory,
    RuleEvidenceKind,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.rule_confidence import (
    RuleConfidence,
    RuleConfidenceBasis,
    RuleConfidenceCalibrationStatus,
    RuleConfidenceLevel,
)
from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceConfidence,
    EvidenceConfidenceBasis,
    EvidenceConfidenceDerivationStatus,
    EvidenceConfidenceLevel,
    EvidenceKind,
    EvidenceLocation,
    EvidenceProductionMode,
    EvidenceRef,
    TraceabilityValidationError,
)
from codestrata.reporting.customer_universe import CustomerFinding, customer_finding_json


def _rule(
    level: RuleConfidenceLevel = RuleConfidenceLevel.HIGH,
) -> RuleConfidence:
    basis = (
        RuleConfidenceBasis.EXACT_SIGNATURE
        if level is RuleConfidenceLevel.HIGH
        else RuleConfidenceBasis.STATIC_PATTERN
        if level is RuleConfidenceLevel.MODERATE
        else RuleConfidenceBasis.PARTIAL_EXTRACTION
    )
    if level is RuleConfidenceLevel.UNAVAILABLE:
        basis = RuleConfidenceBasis.LEGACY_RULE
    return RuleConfidence(
        level=level,
        basis=(basis,),
        limitations=("rule limitation",),
        calibration_status=(
            RuleConfidenceCalibrationStatus.UNAVAILABLE
            if level is RuleConfidenceLevel.UNAVAILABLE
            else RuleConfidenceCalibrationStatus.DEFINED
        ),
    )


def _evidence(
    level: EvidenceConfidenceLevel = EvidenceConfidenceLevel.HIGH,
    *,
    evidence_id: str = "ev:1",
) -> EvidenceRef:
    basis = (
        EvidenceConfidenceBasis.EXACT_PARSE
        if level is EvidenceConfidenceLevel.HIGH
        else EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN
        if level is EvidenceConfidenceLevel.MODERATE
        else EvidenceConfidenceBasis.PARTIAL_PARSE
        if level is EvidenceConfidenceLevel.LIMITED
        else EvidenceConfidenceBasis.LEGACY_EVIDENCE
    )
    status = (
        EvidenceConfidenceDerivationStatus.UNAVAILABLE
        if level is EvidenceConfidenceLevel.UNAVAILABLE
        else EvidenceConfidenceDerivationStatus.DERIVED
    )
    return EvidenceRef(
        evidence_id=evidence_id,
        kind=EvidenceKind.DECLARATION,
        location=EvidenceLocation(path="a.txt", line_start=1, line_end=1),
        evidence_confidence=EvidenceConfidence(
            level=level,
            basis=(basis,),
            limitations=("evidence limitation",),
            derivation_status=status,
        ),
    )


def test_model_normalizes_and_rejects_invalid_high() -> None:
    confidence = FindingConfidence(
        level=FindingConfidenceLevel.MODERATE,
        basis=(
            FindingConfidenceBasis.MODERATE_RULE_CONFIDENCE,
            FindingConfidenceBasis.MODERATE_RULE_CONFIDENCE,
        ),
        limitations=("b", "a", "a"),
        derivation_status=FindingConfidenceDerivationStatus.DERIVED,
    )
    assert confidence.basis == (FindingConfidenceBasis.MODERATE_RULE_CONFIDENCE,)
    assert confidence.limitations == ("a", "b")
    payload = finding_confidence_to_json(confidence)
    assert list(payload) == sorted(payload)

    with pytest.raises(ValidationError, match="complete traceability"):
        FindingConfidence(
            level=FindingConfidenceLevel.HIGH,
            basis=(FindingConfidenceBasis.HIGH_RULE_CONFIDENCE,),
            derivation_status=FindingConfidenceDerivationStatus.DERIVED,
        )
    with pytest.raises(ValidationError, match="must be UNAVAILABLE"):
        FindingConfidence(
            level=FindingConfidenceLevel.MODERATE,
            basis=(FindingConfidenceBasis.LEGACY_FINDING,),
            derivation_status=FindingConfidenceDerivationStatus.DERIVED,
        )


def test_match_mapping_and_high_derivation() -> None:
    assert (
        match_evidence_confidence_support(MatchEvidenceConfidence.CERTAIN)
        is FindingConfidenceLevel.HIGH
    )
    assert (
        match_evidence_confidence_support(MatchEvidenceConfidence.MEDIUM)
        is FindingConfidenceLevel.MODERATE
    )
    assert (
        match_evidence_confidence_support(MatchEvidenceConfidence.LOW)
        is FindingConfidenceLevel.LIMITED
    )

    ref = _evidence(EvidenceConfidenceLevel.HIGH)
    result = derive_finding_confidence(
        rule_confidence=_rule(RuleConfidenceLevel.HIGH),
        match_evidence_confidence=MatchEvidenceConfidence.CERTAIN,
        evidence_refs=(ref,),
        primary_evidence_id=ref.evidence_id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        shared_rule_platform=True,
    )
    assert result.level is FindingConfidenceLevel.HIGH
    assert result.component_summary.traceability_complete is True


def test_weakest_support_caps() -> None:
    ref = _evidence(EvidenceConfidenceLevel.HIGH)
    moderate_rule = derive_finding_confidence(
        rule_confidence=_rule(RuleConfidenceLevel.MODERATE),
        match_evidence_confidence=MatchEvidenceConfidence.HIGH,
        evidence_refs=(ref,),
        primary_evidence_id=ref.evidence_id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        shared_rule_platform=True,
    )
    assert moderate_rule.level is FindingConfidenceLevel.MODERATE

    limited_evidence = derive_finding_confidence(
        rule_confidence=_rule(RuleConfidenceLevel.HIGH),
        match_evidence_confidence=MatchEvidenceConfidence.HIGH,
        evidence_refs=(_evidence(EvidenceConfidenceLevel.LIMITED),),
        primary_evidence_id="ev:1",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        shared_rule_platform=True,
    )
    assert limited_evidence.level is FindingConfidenceLevel.LIMITED

    low_match = derive_finding_confidence(
        rule_confidence=_rule(RuleConfidenceLevel.HIGH),
        match_evidence_confidence=MatchEvidenceConfidence.LOW,
        evidence_refs=(ref,),
        primary_evidence_id=ref.evidence_id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        shared_rule_platform=True,
    )
    assert low_match.level is FindingConfidenceLevel.LIMITED


def test_severity_does_not_affect_confidence() -> None:
    ref = _evidence()
    kwargs = dict(
        rule_confidence=_rule(),
        match_evidence_confidence=MatchEvidenceConfidence.HIGH,
        evidence_refs=(ref,),
        primary_evidence_id=ref.evidence_id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        shared_rule_platform=True,
    )
    left = derive_finding_confidence(**kwargs)
    right = derive_finding_confidence(**kwargs)
    assert left.level == right.level
    assert left.model_dump() == right.model_dump()


def test_legacy_and_deferred_unavailable() -> None:
    legacy = derive_finding_confidence(
        rule_confidence=None,
        match_evidence_confidence=None,
        shared_rule_platform=False,
    )
    assert legacy.level is FindingConfidenceLevel.UNAVAILABLE
    assert FindingConfidenceBasis.LEGACY_FINDING in legacy.basis

    deferred = derive_finding_confidence(
        rule_confidence=_rule(),
        match_evidence_confidence=MatchEvidenceConfidence.HIGH,
        evidence_refs=(),
        evidence_completeness=EvidenceCompleteness.LEGACY,
        limitations=("evidence_ref_mapping_deferred_for_pack",),
        shared_rule_platform=True,
    )
    assert deferred.level is FindingConfidenceLevel.UNAVAILABLE
    assert "finding_evidence_mapping_deferred_for_pack" in deferred.limitations


def test_mapper_and_customer_json_preserve_finding_confidence() -> None:
    match = security_match(
        rule_id="security.private-key-material",
        title="Private key material",
        summary="A supported private-key signature was found.",
        severity=RuleSeverity.HIGH,
        confidence=MatchEvidenceConfidence.CERTAIN,
        evidence=(
            RuleEvidence(
                kind=RuleEvidenceKind.FILE_LOCATION,
                subject_reference="evidence:1",
                safe_location="config/key.pem",
                message="Exact private-key signature",
                attributes={
                    "evidence_id": "sensitive:key",
                    "content_classifications": "private_key_material",
                    "kind": "private_key",
                },
            ),
        ),
        subject_keys=("config/key.pem",),
    )
    finding = RuleFindingMapper().map_match(match, category=RuleCategory.SECURITY)
    assert finding.finding_confidence.level in {
        FindingConfidenceLevel.HIGH,
        FindingConfidenceLevel.MODERATE,
        FindingConfidenceLevel.LIMITED,
    }
    assert finding.metadata["confidence"] == "certain"
    assert finding.id == Finding.create(
        rule_id=finding.rule_id,
        title=finding.title,
        description=finding.description,
        severity=finding.severity,
        category=finding.category,
        subject_keys=("config/key.pem",),
    ).id

    customer = CustomerFinding(
        id=finding.id,
        rule_id=finding.rule_id,
        title=finding.title,
        description=finding.description,
        severity=finding.severity.value,
        category=finding.category.value,
        source=finding.source.value,
        evidence=(),
        affected_technologies=(),
        metadata=finding.metadata,
        evidence_refs=finding.evidence_refs,
        primary_evidence_id=finding.primary_evidence_id,
        synthesized_from_evidence_ids=finding.synthesized_from_evidence_ids,
        evidence_completeness=finding.evidence_completeness.value,
        limitations=finding.limitations,
        finding_confidence=finding.finding_confidence,
    )
    payload = customer_finding_json(customer)
    assert payload["finding_confidence"]["level"] == finding.finding_confidence.level.value
    assert payload["metadata"]["confidence"] == "certain"
    assert "finding_confidence" not in payload["metadata"]


def test_merge_recomputes_and_rejects_contradictory_rule_confidence() -> None:
    left_ref = _evidence(EvidenceConfidenceLevel.HIGH, evidence_id="ev:a")
    right_ref = _evidence(EvidenceConfidenceLevel.MODERATE, evidence_id="ev:b")
    left = Finding.create(
        rule_id="security.private-key-material",
        title="Private key",
        description="desc",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("a",),
        metadata={
            "confidence": "certain",
            "shared_rule_platform": "true",
            "rule_confidence_level": "high",
            "rule_confidence": _rule().model_dump(mode="json"),
        },
        evidence_refs=(left_ref,),
        primary_evidence_id=left_ref.evidence_id,
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        finding_confidence=derive_finding_confidence(
            rule_confidence=_rule(),
            match_evidence_confidence=MatchEvidenceConfidence.CERTAIN,
            evidence_refs=(left_ref,),
            primary_evidence_id=left_ref.evidence_id,
            evidence_completeness=EvidenceCompleteness.COMPLETE,
            shared_rule_platform=True,
        ),
    )
    right = left.model_copy(
        update={
            "evidence_refs": (right_ref,),
            "primary_evidence_id": right_ref.evidence_id,
        }
    )
    merged = merge_finding_traceability(left, right)
    assert {item.evidence_id for item in merged.evidence_refs} == {"ev:a", "ev:b"}
    assert merged.finding_confidence.level is FindingConfidenceLevel.MODERATE

    contradictory = right.model_copy(
        update={
            "metadata": {
                **right.metadata,
                "rule_confidence_level": "moderate",
                "rule_confidence": _rule(RuleConfidenceLevel.MODERATE).model_dump(
                    mode="json"
                ),
            }
        }
    )
    with pytest.raises(TraceabilityValidationError, match="contradictory Rule Confidence"):
        merge_finding_traceability(left, contradictory)


def test_old_finding_payload_defaults_unavailable() -> None:
    finding = Finding.model_validate(
        {
            "id": "finding:legacy",
            "rule_id": "SEC001",
            "title": "Legacy",
            "description": "Phase-1 style",
            "severity": "high",
            "category": "security",
        }
    )
    assert finding.finding_confidence.level is FindingConfidenceLevel.UNAVAILABLE
