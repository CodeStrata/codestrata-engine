"""Pack-level Finding → EvidenceRef wiring tests."""

from __future__ import annotations

from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.rules.enums import RuleCategory, MatchEvidenceConfidence, RuleEvidenceKind
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleVersion
from codestrata.domain.rules.results import RuleMatch
from codestrata.domain.traceability import EvidenceCompleteness

RuleSeverity = FindingSeverity


def _map(rule_id: str, provenance: str, evidence: tuple[RuleEvidence, ...], category: RuleCategory):
    match = RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse("1.0.0"),
        severity=RuleSeverity.HIGH,
        confidence=MatchEvidenceConfidence.HIGH,
        title="Finding",
        summary="Summary",
        evidence=evidence,
        provenance=provenance,
        subject_keys=("subject-a",),
    )
    finding = RuleFindingMapper().map_match(match, category=category)
    return finding


def test_security_finding_contains_evidence_ref_without_secrets() -> None:
    evidence = (
        RuleEvidence(
            kind=RuleEvidenceKind.CONFIGURATION_KEY,
            subject_reference="ev:sec1",
            message="Literal credential detected",
            safe_location="config/application.yml",
            line_start=4,
            line_end=4,
            attributes={
                "evidence_id": "ev:sec1",
                "redacted_preview": "api_key=***",
                "path": "config/application.yml",
            },
        ),
    )
    first = _map(
        "security.credential-literal",
        "security.core",
        evidence,
        RuleCategory.SECURITY,
    )
    second = _map(
        "security.credential-literal",
        "security.core",
        evidence,
        RuleCategory.SECURITY,
    )
    assert first.id == second.id
    assert first.evidence_refs
    assert first.primary_evidence_id == "ev:sec1"
    assert first.evidence_completeness is EvidenceCompleteness.COMPLETE
    text = str(first.evidence_refs[0].model_dump())
    assert "BEGIN PRIVATE" not in text
    assert "/Users/" not in text
    assert first.evidence_refs[0].location is not None
    assert first.evidence_refs[0].location.path == "config/application.yml"


def test_dependency_finding_contains_evidence_ref() -> None:
    evidence = (
        RuleEvidence(
            kind=RuleEvidenceKind.DEPENDENCY,
            subject_reference="ev:dep1",
            message="Dynamic version",
            safe_location="pom.xml",
            line_start=20,
            line_end=20,
            attributes={
                "evidence_id": "ev:dep1",
                "raw_version": "1.2.+",
                "resolved_version_local": "",
            },
        ),
    )
    finding = _map(
        "dependency.mutable-version",
        "dependency.core",
        evidence,
        RuleCategory.DEPENDENCY,
    )
    assert finding.evidence_refs
    assert finding.primary_evidence_id == "ev:dep1"
    assert finding.evidence_refs[0].location is not None
    assert finding.evidence_refs[0].location.path == "pom.xml"
    assert finding.evidence_refs[0].measurement is not None
    assert finding.evidence_refs[0].measurement.measured_value == "1.2.+"


def test_technical_debt_finding_maps_measurement_and_keeps_id() -> None:
    evidence = (
        RuleEvidence(
            kind=RuleEvidenceKind.SYMBOL,
            subject_reference="com.example.Service#run()",
            message="High cyclomatic complexity",
            safe_location="src/Service.java",
            line_start=10,
            line_end=80,
            attributes={
                "evidence_id": "ev:td1",
                "metric": "cyclomatic",
                "value": "0",
                "threshold": "10",
            },
        ),
    )
    first = _map(
        "technical_debt.excessive-branching",
        "technical_debt.core",
        evidence,
        RuleCategory.TECHNICAL_DEBT,
    )
    second = _map(
        "technical_debt.excessive-branching",
        "technical_debt.core",
        evidence,
        RuleCategory.TECHNICAL_DEBT,
    )
    assert first.id == second.id
    assert first.evidence_refs
    assert first.evidence_refs[0].measurement is not None
    assert first.evidence_refs[0].measurement.measured_value == 0


def test_architecture_pack_is_traceable() -> None:
    evidence = (
        RuleEvidence(
            kind=RuleEvidenceKind.SYMBOL,
            subject_reference="unit:payments",
            message="Framework leakage",
            safe_location="src/payments/Api.java",
            attributes={"evidence_id": "arch-ev-1", "provider_id": "language"},
        ),
    )
    finding = _map(
        "architecture.framework-leakage",
        "architecture.core",
        evidence,
        RuleCategory.ARCHITECTURE,
    )
    assert finding.evidence_refs
    assert finding.evidence_completeness.value != "legacy"
    assert "evidence_ref_mapping_deferred_for_pack" not in finding.limitations
