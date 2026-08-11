"""Tests for RuleEvidence → EvidenceRef mapping."""

from __future__ import annotations

from codestrata.application.traceability import (
    evidence_ref_from_rule_evidence,
    evidence_refs_from_rule_match,
    merge_finding_traceability,
    synthesize_finding_traceability,
)
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingSeverity,
)
from codestrata.domain.rules.enums import MatchEvidenceConfidence, RuleEvidenceKind
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleVersion
from codestrata.domain.rules.results import RuleMatch
from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceKind,
    EvidenceLocation,
    EvidenceRef,
    SnippetRedactionLevel,
    TraceabilityValidationError,
)

RuleSeverity = FindingSeverity


def _match(evidence: tuple[RuleEvidence, ...], *, rule_id: str = "security.credential-literal") -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse("1.0.0"),
        severity=RuleSeverity.HIGH,
        confidence=MatchEvidenceConfidence.HIGH,
        title="Title",
        summary="Summary",
        evidence=evidence,
        provenance="security.core",
        subject_keys=("ev:abc", "path:config/.env"),
    )


def test_preserves_existing_evidence_id_and_location() -> None:
    item = RuleEvidence(
        kind=RuleEvidenceKind.CONFIGURATION_KEY,
        subject_reference="ev:abc123",
        message="Literal credential",
        safe_location="config/.env",
        line_start=3,
        line_end=3,
        attributes={
            "evidence_id": "ev:abc123",
            "redacted_preview": "password=***",
            "pack_id": "security",
        },
    )
    ref = evidence_ref_from_rule_evidence(
        item,
        rule_id="security.credential-literal",
        pack_id="security",
    )
    assert ref is not None
    assert ref.evidence_id == "ev:abc123"
    assert ref.location is not None
    assert ref.location.path == "config/.env"
    assert ref.rule_id == "security.credential-literal"
    assert ref.snippet is not None
    assert ref.snippet.redaction_level is SnippetRedactionLevel.PARTIALLY_REDACTED
    assert "***" in ref.snippet.text


def test_omits_absolute_path_with_limitation() -> None:
    item = RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference="ev:path",
        message="artifact",
        safe_location="/Users/me/repo/secrets.pem",
        attributes={"evidence_id": "ev:path"},
    )
    ref = evidence_ref_from_rule_evidence(item, rule_id="security.private-key-material")
    assert ref is not None
    assert ref.location is None or ref.location.path is None
    assert "unsafe_or_absolute_path_omitted" in ref.limitations


def test_measurement_maps_for_technical_debt() -> None:
    item = RuleEvidence(
        kind=RuleEvidenceKind.SYMBOL,
        subject_reference="com.example.Foo#bar()",
        message="High complexity",
        safe_location="src/Foo.java",
        line_start=10,
        line_end=40,
        attributes={
            "evidence_id": "ev:td1",
            "metric": "cyclomatic",
            "value": "12",
            "threshold": "10",
        },
    )
    ref = evidence_ref_from_rule_evidence(
        item,
        rule_id="technical_debt.excessive-branching",
        pack_id="technical_debt",
    )
    assert ref is not None
    assert ref.measurement is not None
    assert ref.measurement.measured_value == 12
    assert ref.measurement.threshold == 10


def test_zero_measurement_remains_valid() -> None:
    item = RuleEvidence(
        kind=RuleEvidenceKind.SYMBOL,
        subject_reference="Foo#bar()",
        message="ok",
        safe_location="a.py",
        attributes={"evidence_id": "ev:z", "metric": "branches", "value": "0", "threshold": "5"},
    )
    ref = evidence_ref_from_rule_evidence(item, rule_id="technical_debt.excessive-branching")
    assert ref is not None
    assert ref.measurement is not None
    assert ref.measurement.measured_value == 0


def test_match_mapping_deterministic_and_preserves_parents() -> None:
    evidence = (
        RuleEvidence(
            kind=RuleEvidenceKind.DEPENDENCY,
            subject_reference="ev:dep1",
            message="conflict",
            safe_location="pom.xml",
            attributes={
                "evidence_id": "ev:dep1",
                "participating_evidence_ids": "ev:dep2,ev:dep1",
                "raw_version": "1.2.3",
            },
        ),
        RuleEvidence(
            kind=RuleEvidenceKind.DEPENDENCY,
            subject_reference="ev:dep2",
            message="conflict",
            safe_location="pom.xml",
            attributes={"evidence_id": "ev:dep2", "participating_evidence_ids": "ev:dep2,ev:dep1"},
        ),
    )
    first, _, _ = evidence_refs_from_rule_match(
        _match(evidence, rule_id="dependency.conflicting-exact-versions")
    )
    second, _, _ = evidence_refs_from_rule_match(
        _match(evidence, rule_id="dependency.conflicting-exact-versions")
    )
    assert [item.evidence_id for item in first] == [item.evidence_id for item in second]
    assert "ev:dep2" in first[0].parent_evidence_ids


def test_architecture_pack_maps_evidence_refs() -> None:
    evidence = (
        RuleEvidence(
            kind=RuleEvidenceKind.SYMBOL,
            subject_reference="unit:a",
            message="architecture",
            safe_location="src/a.py",
            attributes={"evidence_id": "arch-ev-a", "provider_id": "language"},
        ),
    )
    match = _match(evidence, rule_id="architecture.framework-leakage")
    match = match.model_copy(update={"provenance": "architecture.core"})
    refs, limits, count = evidence_refs_from_rule_match(match)
    assert count == 1
    assert refs
    assert "evidence_ref_mapping_deferred_for_pack" not in limits


def test_merge_unions_evidence_refs_without_changing_id() -> None:
    left = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="a",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("k",),
        evidence_refs=(EvidenceRef(evidence_id="ev:1", location=EvidenceLocation(path="a.env")),),
        primary_evidence_id="ev:1",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )
    right = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="b",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("k",),
        evidence_refs=(EvidenceRef(evidence_id="ev:2"),),
        primary_evidence_id="ev:2",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
        limitations=("extra",),
    )
    assert left.id == right.id
    merged = merge_finding_traceability(left, right)
    assert merged.id == left.id
    assert {item.evidence_id for item in merged.evidence_refs} == {"ev:1", "ev:2"}
    assert merged.synthesized_from_evidence_ids == ("ev:1", "ev:2")
    assert "extra" in merged.limitations


def test_synthesize_partial_when_expected_exceeds_mapped() -> None:
    refs, primary, synthesized, completeness, limits = synthesize_finding_traceability(
        (EvidenceRef(evidence_id="ev:1"),),
        expected_count=2,
    )
    assert primary == "ev:1"
    assert synthesized == ()
    assert completeness is EvidenceCompleteness.PARTIAL
    assert "some_rule_evidence_unmapped" in limits


def test_message_snippet_only_when_redactor_masks() -> None:
    masked = RuleEvidence(
        kind=RuleEvidenceKind.CONFIGURATION_KEY,
        subject_reference="ev:sec",
        message="password=SuperSecretValue123!",
        safe_location="app.env",
        attributes={"evidence_id": "ev:sec"},
    )
    ref = evidence_ref_from_rule_evidence(masked, rule_id="security.credential-literal")
    assert ref is not None
    assert "SuperSecretValue123!" not in str(ref.model_dump())
    assert ref.snippet is not None
    assert ref.snippet.redaction_level is SnippetRedactionLevel.PARTIALLY_REDACTED

    plain = RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference="ev:plain",
        message="No secrets here",
        safe_location="readme.md",
        attributes={"evidence_id": "ev:plain"},
    )
    plain_ref = evidence_ref_from_rule_evidence(plain, rule_id="security.credential-literal")
    assert plain_ref is not None
    assert plain_ref.snippet is None
    assert "snippet_omitted_unverified_redaction" in plain_ref.limitations


def test_schema_version_unchanged_by_slice() -> None:
    from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION

    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"

    left = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="a",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("k",),
        evidence_refs=(
            EvidenceRef(
                evidence_id="ev:same",
                kind=EvidenceKind.CONFIGURATION,
                location=EvidenceLocation(path="a.env"),
            ),
        ),
        primary_evidence_id="ev:same",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )
    right = Finding.create(
        rule_id="security.credential-literal",
        title="Literal credential",
        description="b",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        subject_keys=("k",),
        evidence_refs=(
            EvidenceRef(
                evidence_id="ev:same",
                kind=EvidenceKind.FILE_LOCATION,
                location=EvidenceLocation(path="b.env"),
            ),
        ),
        primary_evidence_id="ev:same",
        evidence_completeness=EvidenceCompleteness.COMPLETE,
    )
    try:
        merge_finding_traceability(left, right)
        raise AssertionError("expected TraceabilityValidationError")
    except TraceabilityValidationError as error:
        assert "contradictory" in str(error).lower()
