from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.rules.confidence_catalog import (
    RULE_CONFIDENCE_CATALOG,
    confidence_for_rule,
)
from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.legacy_adapter import LegacyRuleAdapter
from codestrata.application.rules.security.helpers import match as security_match
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.rules.enums import (
    MatchEvidenceConfidence,
    RuleCategory,
    RuleEvidenceKind,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.models import RuleContext, RuleResult
from codestrata.domain.rules.rule_confidence import (
    RuleConfidenceBasis,
    RuleConfidenceCalibrationStatus,
    RuleConfidenceLevel,
)
from codestrata.domain.rules.results import RuleMatch
from codestrata.reporting.customer_universe import CustomerFinding, customer_finding_json


class _LegacyRule:
    def id(self) -> str:
        return "legacy.example"

    def name(self) -> str:
        return "Legacy example"

    def description(self) -> str:
        return "Legacy rule used by the confidence adapter test."

    def supported_languages(self) -> frozenset[str]:
        return frozenset()

    def evaluate(self, context: RuleContext) -> RuleResult:
        _ = context
        return RuleResult(rule_id=self.id())


def _sample_security_match() -> RuleMatch:
    return security_match(
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
            ),
        ),
        subject_keys=("config/key.pem",),
    )


def test_catalog_covers_every_registered_production_rule() -> None:
    service = create_rule_analysis_service()
    registered = {str(view.metadata.rule_id) for view in service.list_rules()}
    assert registered
    assert registered <= RULE_CONFIDENCE_CATALOG.keys()
    assert all(
        view.metadata.confidence == confidence_for_rule(str(view.metadata.rule_id))
        for view in service.list_rules()
    )
    assert all(
        view.metadata.confidence.calibration_status
        is not RuleConfidenceCalibrationStatus.VALIDATION_SUPPORTED
        or (
            view.metadata.confidence.validation_support is not None
            and view.metadata.confidence.validation_support.true_positives >= 1
        )
        for view in service.list_rules()
    )


def test_rule_metadata_requires_inherent_confidence() -> None:
    with pytest.raises(ValidationError, match="confidence"):
        RuleMetadata(
            rule_id="fixture.missing-confidence",
            version=RuleVersion.parse("1.0.0"),
            title="Missing confidence",
            description="Confidence must be required.",
            category=RuleCategory.PLATFORM,
            default_severity=FindingSeverity.LOW,
        )


def test_security_match_and_finding_preserve_both_confidence_meanings() -> None:
    match = _sample_security_match()
    assert match.confidence is MatchEvidenceConfidence.CERTAIN
    assert match.rule_confidence == confidence_for_rule(
        "security.private-key-material"
    )

    finding = RuleFindingMapper().map_match(match, category=RuleCategory.SECURITY)
    assert finding.metadata["confidence"] == "certain"
    assert finding.metadata["rule_confidence"]["level"] == "high"
    assert finding.metadata["rule_confidence_level"] == "high"
    assert finding.metadata["rule_confidence_basis"] == "exact_signature"
    assert "inspected repository content" in finding.metadata[
        "rule_confidence_limitations"
    ]
    assert finding.metadata["rule_confidence_calibration_status"] == "defined"
    assert finding.finding_confidence.level.value in {
        "high",
        "moderate",
        "limited",
        "unavailable",
    }
    assert "finding_confidence" not in finding.metadata


def test_customer_json_promotes_rule_confidence_additively() -> None:
    finding = RuleFindingMapper().map_match(
        _sample_security_match(),
        category=RuleCategory.SECURITY,
    )
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
    )
    payload = customer_finding_json(customer)
    assert payload["rule_confidence"] == payload["metadata"]["rule_confidence"]


def test_legacy_adapter_uses_unavailable_rule_confidence() -> None:
    confidence = LegacyRuleAdapter(_LegacyRule()).metadata.confidence
    assert confidence.level is RuleConfidenceLevel.UNAVAILABLE
    assert confidence.basis == (RuleConfidenceBasis.LEGACY_RULE,)
    assert (
        confidence.calibration_status
        is RuleConfidenceCalibrationStatus.UNAVAILABLE
    )


def test_match_evidence_confidence_rename_preserves_values() -> None:
    assert [item.value for item in MatchEvidenceConfidence] == [
        "low",
        "medium",
        "high",
        "certain",
    ]
