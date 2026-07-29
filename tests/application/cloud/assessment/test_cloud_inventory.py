"""Cloud assessment inventory tests (Phase 4.7.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.cloud.assessment.artifacts import (
    cloud_assessment_payload as build_cloud_assessment_payload,
)
from codestrata.application.cloud.assessment.artifacts import (
    write_cloud_assessment_artifact,
)
from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.application.cloud.assessment.inventory import (
    TECHNOLOGY_FAMILY_IDS,
    build_confidence_inventory,
    build_finding_inventory,
    build_rule_inventory,
    build_severity_inventory,
    build_technology_family_inventory,
    execution_facts_from_status_map,
)
from codestrata.domain.cloud.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.cloud.ids import (
    HYGIENE_RULE_IDS,
    RULE_CONTAINERIZATION,
    RULE_DEPLOYMENT_PIPELINE,
    RULE_KUBERNETES,
    RULE_PLATFORM_DETECTED,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
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
        category=FindingCategory.CLOUD,
        metadata=base,
    )


def test_finding_inventory_id_refs_only() -> None:
    findings = (
        _finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-1"),
        _finding(
            rule_id=RULE_KUBERNETES,
            finding_id="f-2",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    inventory = build_finding_inventory(findings)
    assert inventory.finding_ids == ("f-1", "f-2")
    assert inventory.finding_count == 2
    assert inventory.rule_counts == {
        RULE_CONTAINERIZATION: 1,
        RULE_KUBERNETES: 1,
    }
    assert inventory.severity_counts == {"informational": 1, "low": 1}
    assert inventory.confidence_counts == {"high": 1, "medium": 1}


def test_rule_inventory_applicable_vs_matched() -> None:
    findings = (_finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-1"),)
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_CONTAINERIZATION] = "matched"
    status_map[RULE_PLATFORM_DETECTED] = "not_applicable"
    facts = execution_facts_from_status_map(status_map)
    inventory = build_rule_inventory(findings=findings, execution_facts=facts)
    assert inventory.rules_planned == len(HYGIENE_RULE_IDS)
    assert inventory.rules_executed == len(HYGIENE_RULE_IDS)
    assert inventory.rules_matched == 1
    assert inventory.rules_not_applicable == 1
    assert inventory.rules_failed == 0
    by_id = {item.rule_id: item for item in inventory.entries}
    assert by_id[RULE_CONTAINERIZATION].finding_count == 1
    assert by_id[RULE_CONTAINERIZATION].evaluation_status == "matched"
    assert by_id[RULE_PLATFORM_DETECTED].evaluation_status == "not_applicable"


def test_severity_and_confidence_buckets() -> None:
    findings = (
        _finding(
            rule_id=RULE_CONTAINERIZATION,
            finding_id="f-1",
            severity=FindingSeverity.LOW,
            confidence="high",
        ),
        _finding(
            rule_id=RULE_KUBERNETES,
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


def test_technology_family_coverage() -> None:
    findings = (
        _finding(
            rule_id=RULE_CONTAINERIZATION,
            finding_id="f-ctr",
            metadata={"container_kinds": "docker,docker_compose"},
        ),
        _finding(
            rule_id=RULE_KUBERNETES,
            finding_id="f-k8s",
            metadata={"orchestration_kinds": "kubernetes"},
        ),
        _finding(
            rule_id=RULE_DEPLOYMENT_PIPELINE,
            finding_id="f-dep",
            metadata={"deployment_systems": "github_actions"},
        ),
    )
    inventory = build_technology_family_inventory(findings)
    assert inventory.families_total == len(TECHNOLOGY_FAMILY_IDS)
    assert inventory.families_observed == 3
    by_id = {item.family_id: item for item in inventory.entries}
    assert by_id["containers"].observed is True
    assert by_id["containers"].technologies == ("docker", "docker_compose")
    assert by_id["orchestration"].observed is True
    assert by_id["deployment_pipelines"].observed is True
    assert by_id["platforms"].observed is False
    assert by_id["platforms"].finding_ids == ()


def test_empty_assessment_inventories_graceful() -> None:
    section = CloudAssessmentAssembler().assemble_empty(repository_id="repo:empty")
    assert section.section_version == SECTION_SCHEMA_VERSION
    assert section.finding_inventory.finding_count == 0
    assert section.finding_inventory.finding_ids == ()
    assert section.severity_inventory.buckets == ()
    assert section.confidence_inventory.buckets == ()
    assert section.rule_inventory.rules_matched == 0
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)
    assert section.technology_family_inventory.families_observed == 0
    assert section.technology_family_inventory.families_total == 7


def test_assemble_wires_inventories(tmp_path: Path) -> None:
    findings = (
        _finding(
            rule_id=RULE_CONTAINERIZATION,
            finding_id="f-a",
            metadata={"container_kinds": "docker"},
        ),
        _finding(
            rule_id=RULE_KUBERNETES,
            finding_id="f-b",
            severity=FindingSeverity.LOW,
            confidence="medium",
            metadata={"orchestration_kinds": "kubernetes"},
        ),
    )
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_CONTAINERIZATION] = "matched"
    status_map[RULE_KUBERNETES] = "matched"
    facts = execution_facts_from_status_map(status_map)
    section = CloudAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        rule_execution_facts=facts,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        evidence_pipeline="repository_cloud",
        evidence_fingerprint="inv-fp",
    )
    assert section.section_version == "1.2.0"
    assert section.finding_inventory.finding_count == 2
    assert section.finding_ids == ("f-a", "f-b")
    assert section.rule_inventory.rules_matched == 2
    assert section.technology_family_inventory.families_observed == 2
    assert section.synthesis.themes
    assert section.theme_ids
    payload = dumps_stable_json(build_cloud_assessment_payload(section))
    assert '"finding_inventory"' in payload
    assert '"technology_family_inventory"' in payload
    assert '"synthesis"' in payload
    assert '"hotspots"' not in payload
    written = write_cloud_assessment_artifact(section, tmp_path)
    assert written.path.read_text(encoding="utf-8") == payload


def test_inventory_deterministic_byte_identical(tmp_path: Path) -> None:
    findings = [
        _finding(rule_id=RULE_CONTAINERIZATION, finding_id="f-2"),
        _finding(rule_id=RULE_KUBERNETES, finding_id="f-1"),
    ]
    reversed_findings = list(reversed(findings))
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_CONTAINERIZATION] = "matched"
    status_map[RULE_KUBERNETES] = "matched"
    facts = execution_facts_from_status_map(status_map)
    left = CloudAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(findings),
        rule_execution_facts=facts,
        evidence_fingerprint="same",
        configuration_payload="same-config",
    )
    right = CloudAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(reversed_findings),
        rule_execution_facts=tuple(reversed(facts)),
        evidence_fingerprint="same",
        configuration_payload="same-config",
    )
    left_write = write_cloud_assessment_artifact(left, tmp_path / "a")
    right_write = write_cloud_assessment_artifact(right, tmp_path / "b")
    assert left_write.path.read_bytes() == right_write.path.read_bytes()
