"""Test assessment inventory tests (Phase 4.6.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.testing.assessment.artifacts import (
    testing_assessment_payload as build_testing_assessment_payload,
)
from codestrata.application.testing.assessment.artifacts import (
    write_testing_assessment_artifact,
)
from codestrata.application.testing.assessment.assembler import TestAssessmentAssembler
from codestrata.application.testing.assessment.inventory import (
    build_confidence_inventory,
    build_finding_inventory,
    build_rule_inventory,
    build_severity_inventory,
    execution_facts_from_status_map,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    RepositoryTestingParseStatus,
    TestFileRole,
    TestMarkerType,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
    MarkerFactEvidence,
    RepositoryTestingEvidenceCoverage,
    TestFileCandidateEvidence,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.testing.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.testing.ids import (
    HYGIENE_RULE_IDS,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)
from codestrata.services.artifact_serialization import dumps_stable_json


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _evidence() -> AggregatedRepositoryTestingEvidence:
    return AggregatedRepositoryTestingEvidence(
        repository_id="repo:fixture",
        status=RepositoryTestingParseStatus.SUCCEEDED,
        file_candidates=(
            TestFileCandidateEvidence(
                evidence_id="cand:tests/a.py",
                path="tests/a.py",
                role=TestFileRole.UNIT_TEST,
                provenance=_prov(),
            ),
        ),
        marker_facts=(
            MarkerFactEvidence(
                evidence_id="marker:tests/a.py:disabled",
                path="tests/a.py",
                marker_type=TestMarkerType.DISABLED,
                marker_text="@Disabled",
                provenance=_prov(),
            ),
        ),
        coverage=RepositoryTestingEvidenceCoverage(
            candidate_files_inspected=1,
            marker_facts=1,
            languages_represented=("python",),
        ),
        evidence_fingerprint="inv-fp-1",
    )


def _finding(
    *,
    rule_id: str,
    finding_id: str,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    confidence: str = "high",
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=severity,
        category=FindingCategory.TESTING,
        metadata={"confidence": confidence},
    )


def test_finding_inventory_id_refs_only() -> None:
    findings = (
        _finding(rule_id=RULE_DISABLED_OR_SKIPPED, finding_id="f-1"),
        _finding(
            rule_id=RULE_UNCONFIRMED_CANDIDATES,
            finding_id="f-2",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    inventory = build_finding_inventory(findings)
    assert inventory.finding_ids == ("f-1", "f-2")
    assert inventory.finding_count == 2
    assert inventory.rule_counts == {
        RULE_DISABLED_OR_SKIPPED: 1,
        RULE_UNCONFIRMED_CANDIDATES: 1,
    }
    assert inventory.severity_counts == {"low": 1, "medium": 1}
    assert inventory.confidence_counts == {"high": 1, "medium": 1}


def test_rule_inventory_applicable_vs_matched() -> None:
    findings = (_finding(rule_id=RULE_DISABLED_OR_SKIPPED, finding_id="f-1"),)
    facts = execution_facts_from_status_map(
        {
            RULE_DISABLED_OR_SKIPPED: "matched",
            RULE_UNCONFIRMED_CANDIDATES: "not_matched",
            "testing.test-003": "not_applicable",
            RULE_COVERAGE_WITHOUT_CI_INVOCATION: "not_matched",
        }
    )
    inventory = build_rule_inventory(findings=findings, execution_facts=facts)
    assert inventory.rules_planned == len(HYGIENE_RULE_IDS)
    assert inventory.rules_executed == 4
    assert inventory.rules_matched == 1
    assert inventory.rules_not_matched == 2
    assert inventory.rules_not_applicable == 1
    assert inventory.rules_failed == 0
    by_id = {item.rule_id: item for item in inventory.entries}
    assert by_id[RULE_DISABLED_OR_SKIPPED].finding_count == 1
    assert by_id[RULE_DISABLED_OR_SKIPPED].evaluation_status == "matched"
    assert by_id[RULE_UNCONFIRMED_CANDIDATES].finding_count == 0
    assert by_id[RULE_UNCONFIRMED_CANDIDATES].evaluation_status == "not_matched"


def test_severity_and_confidence_buckets() -> None:
    findings = (
        _finding(
            rule_id=RULE_DISABLED_OR_SKIPPED,
            finding_id="f-1",
            severity=FindingSeverity.HIGH,
            confidence="high",
        ),
        _finding(
            rule_id=RULE_UNCONFIRMED_CANDIDATES,
            finding_id="f-2",
            severity=FindingSeverity.HIGH,
            confidence="low",
        ),
    )
    severity = build_severity_inventory(findings)
    confidence = build_confidence_inventory(findings)
    assert [(item.key, item.count) for item in severity.buckets] == [("high", 2)]
    assert [(item.key, item.count) for item in confidence.buckets] == [
        ("high", 1),
        ("low", 1),
    ]


def test_empty_assessment_inventories_graceful() -> None:
    section = TestAssessmentAssembler().assemble_empty(repository_id="repo:empty")
    assert section.section_version == SECTION_SCHEMA_VERSION
    assert section.finding_inventory.finding_count == 0
    assert section.finding_inventory.finding_ids == ()
    assert section.severity_inventory.buckets == ()
    assert section.confidence_inventory.buckets == ()
    assert section.rule_inventory.rules_matched == 0
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)


def test_assemble_wires_inventories(tmp_path: Path) -> None:
    findings = (
        _finding(rule_id=RULE_DISABLED_OR_SKIPPED, finding_id="f-a"),
        _finding(
            rule_id=RULE_UNCONFIRMED_CANDIDATES,
            finding_id="f-b",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    facts = execution_facts_from_status_map(
        {
            RULE_DISABLED_OR_SKIPPED: "matched",
            RULE_UNCONFIRMED_CANDIDATES: "matched",
            "testing.test-003": "not_matched",
            RULE_COVERAGE_WITHOUT_CI_INVOCATION: "not_matched",
        }
    )
    section = TestAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        evidence=_evidence(),
        pack_enabled=True,
        rules_executed=4,
        rules_matched=2,
        rules_not_matched=2,
        rule_execution_facts=facts,
        evidence_pipeline="repository_testing",
        evidence_fingerprint="inv-fp-1",
    )
    assert section.section_version == "1.2.0"
    assert section.metadata.get("assessment_milestone") == "4.6.5"
    assert section.finding_inventory.finding_ids == ("f-a", "f-b")
    assert section.finding_inventory.rule_counts[RULE_DISABLED_OR_SKIPPED] == 1
    assert section.severity_inventory.buckets
    assert section.confidence_inventory.buckets
    assert section.rule_inventory.rules_matched == 2
    assert section.rule_inventory.rules_not_matched == 2
    # Finding IDs only — no nested Finding objects in inventory JSON.
    payload = build_testing_assessment_payload(section)
    dumped = dumps_stable_json(payload)
    assert '"finding_inventory"' in dumped
    assert '"rule_inventory"' in dumped
    assert '"severity_inventory"' in dumped
    assert '"confidence_inventory"' in dumped
    assert '"hotspots"' not in dumped
    assert "f-a" in dumped
    assert section.finding_inventory.finding_ids == ("f-a", "f-b")
    assert section.themes
    assert section.conclusions
    assert section.recommendations
    assert section.synthesis.overall_posture_summary
    written = write_testing_assessment_artifact(section, tmp_path)
    assert written.path.read_text(encoding="utf-8") == dumped


def test_inventory_deterministic_byte_identical(tmp_path: Path) -> None:
    findings = (
        _finding(rule_id=RULE_UNCONFIRMED_CANDIDATES, finding_id="f-2"),
        _finding(rule_id=RULE_DISABLED_OR_SKIPPED, finding_id="f-1"),
    )
    facts = execution_facts_from_status_map(
        {
            RULE_DISABLED_OR_SKIPPED: "matched",
            RULE_UNCONFIRMED_CANDIDATES: "matched",
            "testing.test-003": "not_matched",
            RULE_COVERAGE_WITHOUT_CI_INVOCATION: "not_matched",
        }
    )
    assembler = TestAssessmentAssembler()
    left = assembler.assemble(
        repository_id="repo:fixture",
        findings=findings,
        evidence=_evidence(),
        rule_execution_facts=facts,
        rules_executed=4,
        rules_matched=2,
        rules_not_matched=2,
        evidence_fingerprint="inv-fp-1",
        configuration_payload="same-config",
    )
    right = assembler.assemble(
        repository_id="repo:fixture",
        findings=tuple(reversed(findings)),
        evidence=_evidence(),
        rule_execution_facts=tuple(reversed(facts)),
        rules_executed=4,
        rules_matched=2,
        rules_not_matched=2,
        evidence_fingerprint="inv-fp-1",
        configuration_payload="same-config",
    )
    assert dumps_stable_json(build_testing_assessment_payload(left)) == dumps_stable_json(
        build_testing_assessment_payload(right)
    )
    write_testing_assessment_artifact(left, tmp_path / "a")
    write_testing_assessment_artifact(right, tmp_path / "b")
    assert (tmp_path / "a" / "testing-assessment.json").read_bytes() == (
        tmp_path / "b" / "testing-assessment.json"
    ).read_bytes()
