"""AI Readiness assessment inventory tests (Phase 4.8.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.ai_readiness.assessment.artifacts import (
    ai_readiness_assessment_payload as build_ai_readiness_assessment_payload,
)
from codestrata.application.ai_readiness.assessment.artifacts import (
    write_ai_readiness_assessment_artifact,
)
from codestrata.application.ai_readiness.assessment.assembler import AiReadinessAssessmentAssembler
from codestrata.application.ai_readiness.assessment.inventory import (
    CAPABILITY_FAMILY_IDS,
    build_capability_family_inventory,
    build_confidence_inventory,
    build_finding_inventory,
    build_rule_inventory,
    build_severity_inventory,
    execution_facts_from_status_map,
)
from codestrata.domain.ai_readiness.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.ai_readiness.ids import (
    HYGIENE_RULE_IDS,
    RULE_API_BOUNDARIES,
    RULE_ARCHITECTURE_DOCS,
    RULE_BROAD_FOUNDATIONS,
    RULE_LLM_SDK,
    RULE_MCP_TOOLS,
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
        category=FindingCategory.AI_READINESS,
        metadata=base,
    )


def test_empty_findings_capability_families() -> None:
    inventory = build_capability_family_inventory(())
    assert inventory.families_total == 7
    assert inventory.families_observed == 0
    assert len(inventory.entries) == len(CAPABILITY_FAMILY_IDS)
    assert all(item.observed is False for item in inventory.entries)
    assert tuple(item.family_id for item in inventory.entries) == CAPABILITY_FAMILY_IDS


def test_finding_inventory_id_refs_only() -> None:
    findings = (
        _finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-1"),
        _finding(
            rule_id=RULE_LLM_SDK,
            finding_id="f-2",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    inventory = build_finding_inventory(findings)
    assert inventory.finding_ids == ("f-1", "f-2")
    assert inventory.finding_count == 2
    assert inventory.rule_counts == {
        RULE_API_BOUNDARIES: 1,
        RULE_LLM_SDK: 1,
    }
    assert inventory.severity_counts == {"informational": 1, "low": 1}
    assert inventory.confidence_counts == {"high": 1, "medium": 1}
    payload = dumps_stable_json(inventory.model_dump(mode="json"))
    assert '"finding_ids"' in payload
    assert '"title"' not in payload
    assert '"description"' not in payload
    assert RULE_API_BOUNDARIES in payload


def test_rule_inventory_applicable_vs_matched() -> None:
    findings = (_finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-1"),)
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_API_BOUNDARIES] = "matched"
    status_map[RULE_ARCHITECTURE_DOCS] = "not_applicable"
    facts = execution_facts_from_status_map(status_map)
    inventory = build_rule_inventory(findings=findings, execution_facts=facts)
    assert inventory.rules_planned == len(HYGIENE_RULE_IDS)
    assert inventory.rules_executed == len(HYGIENE_RULE_IDS)
    assert inventory.rules_matched == 1
    assert inventory.rules_not_applicable == 1
    assert inventory.rules_failed == 0
    by_id = {item.rule_id: item for item in inventory.entries}
    assert by_id[RULE_API_BOUNDARIES].finding_count == 1
    assert by_id[RULE_API_BOUNDARIES].evaluation_status == "matched"
    assert by_id[RULE_ARCHITECTURE_DOCS].evaluation_status == "not_applicable"


def test_severity_and_confidence_buckets() -> None:
    findings = (
        _finding(
            rule_id=RULE_API_BOUNDARIES,
            finding_id="f-1",
            severity=FindingSeverity.LOW,
            confidence="high",
        ),
        _finding(
            rule_id=RULE_LLM_SDK,
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


def test_capability_family_from_rule_ids() -> None:
    findings = (
        _finding(
            rule_id=RULE_API_BOUNDARIES,
            finding_id="f-api",
            metadata={"api_boundary_kinds": "rest,graphql"},
        ),
        _finding(
            rule_id=RULE_LLM_SDK,
            finding_id="f-llm",
            metadata={"llm_kinds": "openai"},
        ),
        _finding(
            rule_id=RULE_MCP_TOOLS,
            finding_id="f-mcp",
            metadata={"tool_mcp_kinds": "mcp_server"},
        ),
    )
    inventory = build_capability_family_inventory(findings)
    assert inventory.families_total == len(CAPABILITY_FAMILY_IDS)
    assert inventory.families_observed == 3
    by_id = {item.family_id: item for item in inventory.entries}
    assert by_id["api_boundaries"].observed is True
    assert by_id["api_boundaries"].signals == ("graphql", "rest")
    assert by_id["ai_integrations"].observed is True
    assert by_id["tool_mcp"].observed is True
    assert by_id["documentation_metadata"].observed is False
    assert by_id["documentation_metadata"].finding_ids == ()


def test_ai_060_families_metadata_maps_multiple() -> None:
    findings = (
        _finding(
            rule_id=RULE_BROAD_FOUNDATIONS,
            finding_id="f-060",
            metadata={
                "families": "api_boundary,documentation,ai_integration,tool_mcp",
            },
        ),
    )
    inventory = build_capability_family_inventory(findings)
    assert inventory.families_observed == 4
    by_id = {item.family_id: item for item in inventory.entries}
    assert by_id["api_boundaries"].observed is True
    assert by_id["documentation_metadata"].observed is True
    assert by_id["ai_integrations"].observed is True
    assert by_id["tool_mcp"].observed is True
    assert by_id["data_retrieval"].observed is False


def test_empty_assessment_inventories_graceful() -> None:
    section = AiReadinessAssessmentAssembler().assemble_empty(repository_id="repo:empty")
    assert section.section_version == SECTION_SCHEMA_VERSION
    assert section.section_version == "1.2.0"
    assert section.finding_inventory.finding_count == 0
    assert section.finding_inventory.finding_ids == ()
    assert section.severity_inventory.buckets == ()
    assert section.confidence_inventory.buckets == ()
    assert section.rule_inventory.rules_matched == 0
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)
    assert section.capability_family_inventory.families_observed == 0
    assert section.capability_family_inventory.families_total == 7


def test_assemble_wires_inventories(tmp_path: Path) -> None:
    findings = (
        _finding(
            rule_id=RULE_API_BOUNDARIES,
            finding_id="f-a",
            metadata={"api_boundary_kinds": "rest"},
        ),
        _finding(
            rule_id=RULE_LLM_SDK,
            finding_id="f-b",
            severity=FindingSeverity.LOW,
            confidence="medium",
            metadata={"llm_kinds": "openai"},
        ),
    )
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_API_BOUNDARIES] = "matched"
    status_map[RULE_LLM_SDK] = "matched"
    facts = execution_facts_from_status_map(status_map)
    section = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:fixture",
        findings=findings,
        rule_execution_facts=facts,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        evidence_pipeline="repository_ai_readiness",
        evidence_fingerprint="inv-fp",
    )
    assert section.section_version == "1.2.0"
    assert section.status.value == "succeeded"
    assert section.finding_inventory.finding_count == 2
    assert section.finding_ids == ("f-a", "f-b")
    assert section.rule_inventory.rules_matched == 2
    assert section.capability_family_inventory.families_observed == 2
    payload = dumps_stable_json(build_ai_readiness_assessment_payload(section))
    assert '"finding_inventory"' in payload
    assert '"capability_family_inventory"' in payload
    assert '"synthesis"' in payload
    assert '"hotspots"' not in payload
    assert '"readiness_score"' not in payload
    written = write_ai_readiness_assessment_artifact(section, tmp_path)
    assert written.path.read_text(encoding="utf-8") == payload


def test_assemble_include_findings_false_keeps_rule_inventory() -> None:
    findings = (_finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-1"),)
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_API_BOUNDARIES] = "matched"
    facts = execution_facts_from_status_map(status_map)
    section = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:nofindings",
        findings=findings,
        rule_execution_facts=facts,
        include_findings=False,
    )
    assert section.finding_inventory.finding_count == 0
    assert section.finding_ids == ()
    assert section.capability_family_inventory.families_observed == 0
    assert section.rule_inventory.rules_matched == 1
    assert len(section.rule_inventory.entries) == len(HYGIENE_RULE_IDS)


def test_assemble_zero_findings_succeeded() -> None:
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    facts = execution_facts_from_status_map(status_map)
    section = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:zero",
        findings=(),
        rule_execution_facts=facts,
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert section.status.value == "succeeded"
    assert section.finding_inventory.finding_count == 0
    assert section.rule_inventory.rules_not_matched == len(HYGIENE_RULE_IDS)
    assert section.capability_family_inventory.families_total == 7
    assert section.capability_family_inventory.families_observed == 0


def test_inventory_deterministic_byte_identical(tmp_path: Path) -> None:
    findings = [
        _finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-2"),
        _finding(rule_id=RULE_LLM_SDK, finding_id="f-1"),
    ]
    reversed_findings = list(reversed(findings))
    status_map = {rule_id: "not_matched" for rule_id in HYGIENE_RULE_IDS}
    status_map[RULE_API_BOUNDARIES] = "matched"
    status_map[RULE_LLM_SDK] = "matched"
    facts = execution_facts_from_status_map(status_map)
    left = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(findings),
        rule_execution_facts=facts,
        evidence_fingerprint="same",
        configuration_payload="same-config",
    )
    right = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:det",
        findings=tuple(reversed_findings),
        rule_execution_facts=tuple(reversed(facts)),
        evidence_fingerprint="same",
        configuration_payload="same-config",
    )
    left_write = write_ai_readiness_assessment_artifact(left, tmp_path / "a")
    right_write = write_ai_readiness_assessment_artifact(right, tmp_path / "b")
    assert left_write.path.read_bytes() == right_write.path.read_bytes()
    assert dumps_stable_json(build_ai_readiness_assessment_payload(left)) == dumps_stable_json(
        build_ai_readiness_assessment_payload(right)
    )
