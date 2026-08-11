"""Tests for Evidence Confidence model and policy."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from codestrata.application.traceability.evidence_confidence import (
    EvidenceConfidenceInputs,
    apply_parent_confidence_bounds,
    derive_evidence_confidence,
)
from codestrata.domain.rules.enums import RuleEvidenceKind
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.traceability import (
    EvidenceConfidence,
    EvidenceConfidenceBasis,
    EvidenceConfidenceDerivationStatus,
    EvidenceConfidenceLevel,
    EvidenceKind,
    EvidenceLocation,
    EvidenceProductionMode,
    EvidenceRef,
    LocationPrecision,
    evidence_confidence_to_json,
    evidence_ref_from_stable_dict,
    evidence_ref_to_stable_dict,
)
from codestrata.application.traceability.rule_evidence import evidence_ref_from_rule_evidence


def test_model_normalizes_and_rejects_invalid_high() -> None:
    confidence = EvidenceConfidence(
        level=EvidenceConfidenceLevel.HIGH,
        basis=(
            EvidenceConfidenceBasis.EXACT_PARSE,
            EvidenceConfidenceBasis.EXACT_PARSE,
        ),
        limitations=("b", "a", "a"),
        derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
    )
    assert confidence.basis == (EvidenceConfidenceBasis.EXACT_PARSE,)
    assert confidence.limitations == ("a", "b")
    payload = evidence_confidence_to_json(confidence)
    assert list(payload) == sorted(payload)
    assert json.dumps(payload, sort_keys=True) == json.dumps(
        evidence_confidence_to_json(confidence),
        sort_keys=True,
    )

    with pytest.raises(ValidationError, match="strong basis"):
        EvidenceConfidence(
            level=EvidenceConfidenceLevel.HIGH,
            basis=(EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,),
            derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    with pytest.raises(ValidationError, match="cannot be HIGH"):
        EvidenceConfidence(
            level=EvidenceConfidenceLevel.HIGH,
            basis=(
                EvidenceConfidenceBasis.EXACT_PARSE,
                EvidenceConfidenceBasis.PARTIAL_PARSE,
            ),
            derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    with pytest.raises(ValidationError, match="must be UNAVAILABLE"):
        EvidenceConfidence(
            level=EvidenceConfidenceLevel.MODERATE,
            basis=(EvidenceConfidenceBasis.LEGACY_EVIDENCE,),
            derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
        )


def test_manifest_declaration_and_configuration_are_high() -> None:
    declaration = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.DECLARATION,
            provenance="aggregated_dependency_evidence",
            attributes={
                "evidence_id": "dep:1",
                "normalized_identity": "requests",
                "raw_version": "2.0.0",
            },
            location=EvidenceLocation(path="requirements.txt", line_start=1, line_end=1),
            provider_id="dependency.python",
        )
    )
    assert declaration.level is EvidenceConfidenceLevel.HIGH
    assert EvidenceConfidenceBasis.EXPLICIT_DECLARATION in declaration.basis

    config = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.CONFIGURATION,
            provenance="aggregated_repository_sensitive_evidence",
            attributes={
                "evidence_id": "cfg:1",
                "normalized_key": "ssl.verify",
                "redacted_preview": "[REDACTED]",
                "parse_status": "succeeded",
            },
            location=EvidenceLocation(path="app.yml", line_start=4, line_end=4),
            provider_id="sensitive.core",
        )
    )
    assert config.level is EvidenceConfidenceLevel.HIGH
    assert EvidenceConfidenceBasis.EXPLICIT_CONFIGURATION in config.basis


def test_signature_metric_partial_and_legacy() -> None:
    signature = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.FILE_LOCATION,
            provenance="aggregated_repository_sensitive_evidence",
            attributes={
                "evidence_id": "art:1",
                "content_classifications": "private_key_material",
                "kind": "private_key",
            },
            location=EvidenceLocation(path="keys/id_rsa"),
            provider_id="sensitive.core",
        )
    )
    assert signature.level is EvidenceConfidenceLevel.HIGH
    assert EvidenceConfidenceBasis.EXACT_SIGNATURE in signature.basis

    metric = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.MEASUREMENT,
            provenance="aggregated_complexity_evidence",
            attributes={"metric": "cyclomatic", "value": "12", "evidence_id": "c:1"},
            location=EvidenceLocation(path="a.py", line_start=1, line_end=10),
            has_measurement=True,
            provider_id="language.python",
        )
    )
    assert metric.level is EvidenceConfidenceLevel.HIGH
    assert EvidenceConfidenceBasis.DETERMINISTIC_METRIC in metric.basis

    partial = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.DECLARATION,
            attributes={"parse_status": "partially_succeeded", "evidence_id": "dep:2"},
            provider_id="dependency.maven",
        )
    )
    assert partial.level is EvidenceConfidenceLevel.LIMITED
    assert EvidenceConfidenceBasis.PARTIAL_PARSE in partial.basis

    legacy = derive_evidence_confidence(
        EvidenceConfidenceInputs(production_mode=EvidenceProductionMode.LEGACY)
    )
    assert legacy.level is EvidenceConfidenceLevel.UNAVAILABLE
    assert EvidenceConfidenceBasis.LEGACY_EVIDENCE in legacy.basis


def test_approximate_location_and_static_signal() -> None:
    approx = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.DECLARATION,
            provenance="aggregated_dependency_evidence",
            attributes={"evidence_id": "dep:3", "normalized_identity": "x", "raw_version": "1"},
            location=EvidenceLocation(
                path="pom.xml",
                precision=LocationPrecision.APPROXIMATE,
            ),
            provider_id="dependency.maven",
        )
    )
    assert approx.level is EvidenceConfidenceLevel.MODERATE
    assert EvidenceConfidenceBasis.APPROXIMATE_LOCATION in approx.basis

    signal = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.REPOSITORY_FACT,
            provenance="aggregated_repository_cloud_evidence",
            attributes={"evidence_id": "cloud:1", "path": "Dockerfile"},
            provider_id="cloud.core",
        )
    )
    assert signal.level is EvidenceConfidenceLevel.MODERATE


def test_synthesized_cannot_exceed_parents() -> None:
    weak = EvidenceConfidence(
        level=EvidenceConfidenceLevel.LIMITED,
        basis=(EvidenceConfidenceBasis.PARTIAL_PARSE,),
        limitations=("Partial parent.",),
        derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
    )
    strong = EvidenceConfidence(
        level=EvidenceConfidenceLevel.HIGH,
        basis=(EvidenceConfidenceBasis.EXACT_PARSE,),
        derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
    )
    synthesized = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=EvidenceKind.SYNTHETIC,
            production_mode=EvidenceProductionMode.SYNTHESIZED,
            parent_evidence_ids=("ev:weak", "ev:strong"),
        ),
        parent_confidence={"ev:weak": weak, "ev:strong": strong},
    )
    assert synthesized.level is EvidenceConfidenceLevel.LIMITED
    assert "Partial parent." in synthesized.limitations

    missing = derive_evidence_confidence(
        EvidenceConfidenceInputs(
            production_mode=EvidenceProductionMode.SYNTHESIZED,
            parent_evidence_ids=("ev:missing",),
        ),
        parent_confidence={},
    )
    assert missing.level is EvidenceConfidenceLevel.UNAVAILABLE


def test_rule_evidence_mapping_and_old_payload() -> None:
    item = RuleEvidence(
        kind=RuleEvidenceKind.DEPENDENCY,
        subject_reference="dep:requests",
        message="Declared dependency",
        safe_location="requirements.txt",
        line_start=1,
        line_end=1,
        attributes={
            "evidence_id": "dep:requests",
            "normalized_identity": "requests",
            "raw_version": "2.31.0",
        },
        provenance="aggregated_dependency_evidence",
    )
    ref = evidence_ref_from_rule_evidence(item, rule_id="dependency.mutable-version")
    assert ref is not None
    assert ref.evidence_confidence.level is EvidenceConfidenceLevel.HIGH
    payload = evidence_ref_to_stable_dict(ref)
    assert payload["evidence_confidence"]["level"] == "high"
    assert "finding_confidence" not in payload

    legacy_payload = {"evidence_id": "ev:old"}
    restored = evidence_ref_from_stable_dict(legacy_payload)
    assert restored.evidence_confidence.level is EvidenceConfidenceLevel.UNAVAILABLE
    assert restored.evidence_id == "ev:old"


def test_parent_bounds_on_ref_batch() -> None:
    parent = EvidenceRef(
        evidence_id="ev:parent",
        evidence_confidence=EvidenceConfidence(
            level=EvidenceConfidenceLevel.MODERATE,
            basis=(EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,),
            derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
        ),
    )
    child = EvidenceRef(
        evidence_id="ev:child",
        production_mode=EvidenceProductionMode.SYNTHESIZED,
        parent_evidence_ids=("ev:parent",),
        evidence_confidence=EvidenceConfidence(
            level=EvidenceConfidenceLevel.HIGH,
            basis=(EvidenceConfidenceBasis.EXACT_PARSE,),
            derivation_status=EvidenceConfidenceDerivationStatus.DERIVED,
        ),
    )
    bounded = apply_parent_confidence_bounds((parent, child))
    by_id = {item.evidence_id: item for item in bounded}
    assert by_id["ev:child"].evidence_confidence.level is EvidenceConfidenceLevel.MODERATE
