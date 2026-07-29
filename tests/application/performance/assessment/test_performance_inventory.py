"""Performance assessment inventory tests (Phase 4.9.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.performance.assessment.artifacts import (
    performance_assessment_payload as build_performance_assessment_payload,
)
from codestrata.application.performance.assessment.artifacts import (
    write_performance_assessment_artifact,
)
from codestrata.application.performance.assessment.assembler import PerformanceAssessmentAssembler
from codestrata.application.performance.assessment.inventory import (
    PERFORMANCE_FAMILY_IDS,
    build_confidence_inventory,
    build_finding_inventory,
    build_performance_family_inventory,
    build_rule_inventory,
    build_severity_inventory,
    execution_facts_from_status_map,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.performance.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.performance.ids import (
    HYGIENE_RULE_IDS,
    RULE_BROAD_FOUNDATIONS,
    RULE_CACHING,
    RULE_CONCURRENCY,
    RULE_DATA_ACCESS,
    RULE_FRONTEND_BUNDLE,
)
from codestrata.domain.performance.synthesis.enums import PerformanceSynthesisStatus
from codestrata.services.artifact_serialization import dumps_stable_json


def _finding(
    *,
    rule_id: str,
    finding_id: str,
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
    confidence: str = "high",
    metadata: dict[str, str] | None = None,
) -> Finding:
    base = {"confidence": confidence}
    if metadata:
        base.update(metadata)
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=severity,
        category=FindingCategory.PERFORMANCE,
        metadata=base,
    )


def test_empty_findings_performance_families() -> None:
    inventory = build_performance_family_inventory(())
    assert inventory.families_total == 8
    assert inventory.families_observed == 0
    assert len(inventory.entries) == len(PERFORMANCE_FAMILY_IDS)
    assert all(item.observed is False for item in inventory.entries)
    assert tuple(item.family_id for item in inventory.entries) == PERFORMANCE_FAMILY_IDS


def test_finding_inventory_id_refs_only() -> None:
    findings = (
        _finding(rule_id=RULE_DATA_ACCESS, finding_id="f-1"),
        _finding(
            rule_id=RULE_CACHING,
            finding_id="f-2",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    inventory = build_finding_inventory(findings)
    assert inventory.finding_ids == ("f-1", "f-2")
    assert inventory.finding_count == 2
    assert inventory.rule_counts == {
        RULE_DATA_ACCESS: 1,
        RULE_CACHING: 1,
    }
    assert inventory.severity_counts == {"informational": 1, "low": 1}
    assert inventory.confidence_counts == {"high": 1, "medium": 1}
    payload = dumps_stable_json(inventory.model_dump(mode="json"))
    assert '"finding_ids"' in payload
    assert '"title"' not in payload
    assert '"description"' not in payload
    assert RULE_DATA_ACCESS in payload


def test_rule_inventory_from_execution_facts() -> None:
    findings = (_finding(rule_id=RULE_DATA_ACCESS, finding_id="f-1"),)
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_DATA_ACCESS] = "matched"
    status_map[RULE_CACHING] = "not_applicable"
    facts = execution_facts_from_status_map(status_map)
    inventory = build_rule_inventory(findings=findings, execution_facts=facts)
    assert inventory.rules_planned == len(HYGIENE_RULE_IDS)
    assert inventory.rules_executed == len(HYGIENE_RULE_IDS)
    assert inventory.rules_matched == 1
    assert inventory.rules_not_applicable == 1
    assert inventory.rules_failed == 0
    by_id = {item.rule_id: item for item in inventory.entries}
    assert by_id[RULE_DATA_ACCESS].finding_count == 1
    assert by_id[RULE_DATA_ACCESS].evaluation_status == "matched"
    assert by_id[RULE_CACHING].evaluation_status == "not_applicable"


def test_severity_and_confidence_buckets() -> None:
    findings = (
        _finding(
            rule_id=RULE_DATA_ACCESS,
            finding_id="f-1",
            severity=FindingSeverity.LOW,
            confidence="high",
        ),
        _finding(
            rule_id=RULE_CACHING,
            finding_id="f-2",
            severity=FindingSeverity.LOW,
            confidence="low",
        ),
    )
    severity = build_severity_inventory(findings)
    confidence = build_confidence_inventory(findings)
    assert [(item.key, item.count) for item in severity.buckets] == [("low", 2)]
    assert [(item.key, item.count) for item in confidence.buckets] == [
        ("high", 1),
        ("low", 1),
    ]


def test_family_derivation_from_rule_ids() -> None:
    findings = (
        _finding(
            rule_id=RULE_DATA_ACCESS,
            finding_id="f-data",
            metadata={"data_access_kinds": "jpa,hibernate"},
        ),
        _finding(
            rule_id=RULE_CONCURRENCY,
            finding_id="f-conc",
            metadata={"concurrency_kinds": "executor_service"},
        ),
        _finding(
            rule_id=RULE_FRONTEND_BUNDLE,
            finding_id="f-fe",
            metadata={"frontend_bundle_kinds": "webpack"},
        ),
    )
    inventory = build_performance_family_inventory(findings)
    assert inventory.families_total == len(PERFORMANCE_FAMILY_IDS)
    assert inventory.families_observed == 3
    by_id = {item.family_id: item for item in inventory.entries}
    assert by_id["data_access"].observed is True
    assert by_id["data_access"].signals == ("hibernate", "jpa")
    assert by_id["concurrency_async"].observed is True
    assert by_id["frontend_performance"].observed is True
    assert by_id["caching"].observed is False
    assert by_id["caching"].finding_ids == ()


def test_perf_071_families_metadata_maps_multiple() -> None:
    findings = (
        _finding(
            rule_id=RULE_BROAD_FOUNDATIONS,
            finding_id="f-071",
            metadata={
                "families": "data_access,caching,configuration_controls,concurrency_async",
            },
        ),
    )
    inventory = build_performance_family_inventory(findings)
    assert inventory.families_observed == 4
    by_id = {item.family_id: item for item in inventory.entries}
    assert by_id["data_access"].observed is True
    assert by_id["caching"].observed is True
    assert by_id["configuration_controls"].observed is True
    assert by_id["concurrency_async"].observed is True
    assert by_id["blocking_operations"].observed is False


def test_empty_assessment_inventories_graceful() -> None:
    section = PerformanceAssessmentAssembler().assemble_empty(repository_id="repo:empty")
    assert section.section_version == SECTION_SCHEMA_VERSION
    assert section.section_version == "1.2.0"
    assert section.finding_inventory.finding_count == 0
    assert section.finding_inventory.finding_ids == ()
    assert section.severity_inventory.buckets == ()
    assert section.confidence_inventory.buckets == ()
    assert section.rule_inventory.rules_matched == 0
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)
    assert section.performance_family_inventory.families_observed == 0
    assert section.performance_family_inventory.families_total == 8
    assert section.synthesis.status is PerformanceSynthesisStatus.NOT_REQUESTED


def test_assemble_wires_inventories(tmp_path: Path) -> None:
    findings = (
        _finding(
            rule_id=RULE_DATA_ACCESS,
            finding_id="f-a",
            metadata={"data_access_kinds": "jpa"},
        ),
        _finding(
            rule_id=RULE_CACHING,
            finding_id="f-b",
            severity=FindingSeverity.LOW,
            confidence="medium",
            metadata={"caching_kinds": "caffeine"},
        ),
    )
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_DATA_ACCESS] = "matched"
    status_map[RULE_CACHING] = "matched"
    facts = execution_facts_from_status_map(status_map)
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        rule_execution_facts=facts,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        evidence_pipeline="repository_performance",
        evidence_fingerprint="inv-fp",
    )
    assert section.section_version == "1.2.0"
    assert section.status.value == "succeeded"
    assert section.finding_inventory.finding_count == 2
    assert section.finding_ids == ("f-a", "f-b")
    assert section.rule_inventory.rules_matched == 2
    assert section.performance_family_inventory.families_observed == 2
    assert section.synthesis.status is PerformanceSynthesisStatus.SUCCEEDED
    assert section.themes
    payload = dumps_stable_json(build_performance_assessment_payload(section))
    assert '"finding_inventory"' in payload
    assert '"performance_family_inventory"' in payload
    assert '"synthesis"' in payload
    assert '"themes"' in payload
    assert '"hotspots"' not in payload
    assert '"performance_score"' not in payload
    written = write_performance_assessment_artifact(section, tmp_path)
    assert written.path.read_text(encoding="utf-8") == payload


def test_assemble_include_findings_false_keeps_rule_inventory() -> None:
    findings = (_finding(rule_id=RULE_DATA_ACCESS, finding_id="f-1"),)
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_DATA_ACCESS] = "matched"
    facts = execution_facts_from_status_map(status_map)
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:nofindings",
        findings=findings,
        rule_execution_facts=facts,
        include_findings=False,
    )
    assert section.finding_inventory.finding_count == 0
    assert section.finding_ids == ()
    assert section.performance_family_inventory.families_observed == 0
    assert section.rule_inventory.rules_matched == 1
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)


def test_assemble_zero_findings_succeeded() -> None:
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    facts = execution_facts_from_status_map(status_map)
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:zero",
        findings=(),
        rule_execution_facts=facts,
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert section.status.value == "succeeded"
    assert section.finding_inventory.finding_count == 0
    assert section.rule_inventory.rules_not_matched == len(HYGIENE_RULE_IDS)
    assert section.performance_family_inventory.families_total == 8
    assert section.performance_family_inventory.families_observed == 0
    assert section.synthesis.status is PerformanceSynthesisStatus.EMPTY


def test_schema_version_1_2_0() -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    section = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:schema",
        findings=(),
    )
    assert section.section_version == "1.2.0"


def test_inventory_deterministic_byte_identical(tmp_path: Path) -> None:
    findings = [
        _finding(rule_id=RULE_DATA_ACCESS, finding_id="f-2"),
        _finding(rule_id=RULE_CACHING, finding_id="f-1"),
    ]
    reversed_findings = list(reversed(findings))
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_DATA_ACCESS] = "matched"
    status_map[RULE_CACHING] = "matched"
    facts = execution_facts_from_status_map(status_map)
    left = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(findings),
        rule_execution_facts=facts,
        evidence_fingerprint="same",
        configuration_payload="same-config",
    )
    right = PerformanceAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(reversed_findings),
        rule_execution_facts=tuple(reversed(facts)),
        evidence_fingerprint="same",
        configuration_payload="same-config",
    )
    left_write = write_performance_assessment_artifact(left, tmp_path / "a")
    right_write = write_performance_assessment_artifact(right, tmp_path / "b")
    assert left_write.path.read_bytes() == right_write.path.read_bytes()
    assert dumps_stable_json(build_performance_assessment_payload(left)) == dumps_stable_json(
        build_performance_assessment_payload(right)
    )
