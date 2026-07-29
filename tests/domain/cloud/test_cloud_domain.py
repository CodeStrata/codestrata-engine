"""Cloud Intelligence domain foundation tests (Phase 4.7.1)."""

from __future__ import annotations

from codestrata.application.cloud.assessment.assembler import CloudAssessmentAssembler
from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.domain.cloud.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    CLOUD_ASSESSMENT_FILENAME,
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_diagnostic_id,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.cloud.assessment.models import CloudAssessmentSection
from codestrata.domain.cloud.ids import (
    CLOUD_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    PACK_VERSION,
    RULE_ALIAS_TO_ID,
    RULE_ID_PREFIX,
)
from codestrata.domain.cloud.taxonomy import (
    CLOUD_CATEGORIES,
    CloudCategory,
    coerce_cloud_category,
)
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.enums import RuleCategory
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "cloud.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "cloud."
    assert CLOUD_RULE_IDS == HYGIENE_RULE_IDS
    assert len(HYGIENE_RULE_IDS) == 11
    assert RULE_ALIAS_TO_ID["CLOUD-001"] == "cloud.cloud-001"
    assert RULE_ALIAS_TO_ID["CLOUD-061"] == "cloud.cloud-061"
    assert SECTION_ID == "assessment.cloud"
    assert SCHEMA_NAME == "cloud-assessment"
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert CLOUD_ASSESSMENT_FILENAME == "cloud-assessment.json"
    assert ARTIFACT_SCHEMA_ID == "codestrata.cloud_assessment"


def test_taxonomy_is_deterministic_and_namespaced() -> None:
    assert CloudCategory.EXTERNALIZED_CONFIGURATION.value == ("cloud.externalized_configuration")
    assert CloudCategory.UNKNOWN.value == "cloud.unknown"
    assert CLOUD_CATEGORIES == tuple(CloudCategory)
    assert all(item.value.startswith("cloud.") for item in CLOUD_CATEGORIES)
    values = [item.value for item in CLOUD_CATEGORIES]
    assert len(values) == len(set(values))
    joined = " ".join(values)
    assert "cloud readiness score" not in joined
    assert "risk rating" not in joined
    assert "compliance grade" not in joined


def test_coerce_unknown_taxonomy_values() -> None:
    assert coerce_cloud_category("cloud.statelessness") is CloudCategory.STATELESSNESS
    assert coerce_cloud_category("statelessness") is CloudCategory.STATELESSNESS
    assert (
        coerce_cloud_category("cloud.externalized-configuration")
        is CloudCategory.EXTERNALIZED_CONFIGURATION
    )
    assert coerce_cloud_category("not-a-real-category") is CloudCategory.UNKNOWN
    assert coerce_cloud_category("") is CloudCategory.UNKNOWN
    assert coerce_cloud_category(None) is CloudCategory.UNKNOWN
    assert coerce_cloud_category(CloudCategory.PORTABILITY) is CloudCategory.PORTABILITY


def test_finding_category_cloud_mapping() -> None:
    assert FindingCategory.CLOUD.value == "cloud"
    assert RuleCategory.CLOUD.value == "cloud"
    assert _CATEGORY_MAP[RuleCategory.CLOUD] is FindingCategory.CLOUD
    assert _CATEGORY_MAP[RuleCategory.TESTING] is FindingCategory.TESTING
    assert _CATEGORY_MAP[RuleCategory.SECURITY] is FindingCategory.SECURITY


def test_identifiers_are_deterministic_and_non_random() -> None:
    left = build_assessment_id(
        repository_id="repo:demo",
        status="succeeded",
        configuration_fingerprint="abc",
    )
    right = build_assessment_id(
        repository_id="repo:demo",
        status="succeeded",
        configuration_fingerprint="abc",
    )
    assert left == right
    assert left.startswith("cloud-assessment:")
    assert build_limitation_id(category="x", summary="y").startswith("cloud-limitation:")
    assert build_diagnostic_id(code="a", message="b").startswith("cloud-diagnostic:")
    assert build_trace_edge_id(relation="section_to_pack", source_id="a", target_id="b").startswith(
        "cloud-trace:"
    )
    assert "uuid" not in left
    assert "/Users/" not in left


def test_section_forbids_deferred_analysis_fields() -> None:
    fields = CloudAssessmentSection.model_fields
    forbidden = {
        "hotspots",
        "inventories",
        "cloud_score",
        "readiness_score",
        "risk_rating",
        "compliance_grade",
    }
    assert forbidden.isdisjoint(fields.keys())
    assert "finding_inventory" in fields
    assert "technology_family_inventory" in fields
    assert "synthesis" in fields
    assert "themes" in fields


def test_empty_section_round_trip_deterministic() -> None:
    left = CloudAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    right = CloudAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = CloudAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.schema_name == SCHEMA_NAME
    assert restored.section_version == "1.2.0"
    assert restored.status.value == "succeeded"
    assert restored.finding_ids == ()
    assert restored.finding_inventory.finding_count == 0
    assert restored.execution_summary.cloud_rules_planned == len(HYGIENE_RULE_IDS)
