"""AI Readiness Intelligence domain foundation tests (Phase 4.8.1)."""

from __future__ import annotations

from codestrata.application.ai_readiness.assessment.assembler import AiReadinessAssessmentAssembler
from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.domain.ai_readiness.assessment.identifiers import (
    AI_READINESS_ASSESSMENT_FILENAME,
    ARTIFACT_SCHEMA_ID,
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_diagnostic_id,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.ai_readiness.assessment.models import AiReadinessAssessmentSection
from codestrata.domain.ai_readiness.ids import (
    AI_READINESS_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    PACK_VERSION,
    RULE_ALIAS_TO_ID,
    RULE_API_BOUNDARIES,
    RULE_ID_PREFIX,
    RULE_LIMITED_FOUNDATIONS,
)
from codestrata.domain.ai_readiness.taxonomy import (
    AI_READINESS_CATEGORIES,
    AiReadinessCategory,
    coerce_ai_readiness_category,
)
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.enums import RuleCategory
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "ai_readiness.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "ai_readiness."
    assert AI_READINESS_RULE_IDS == HYGIENE_RULE_IDS
    assert len(HYGIENE_RULE_IDS) == 17
    assert RULE_ALIAS_TO_ID["AI-001"] == RULE_API_BOUNDARIES
    assert RULE_ALIAS_TO_ID["AI-061"] == RULE_LIMITED_FOUNDATIONS
    assert SECTION_ID == "assessment.ai_readiness"
    assert SCHEMA_NAME == "ai-readiness-assessment"
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert AI_READINESS_ASSESSMENT_FILENAME == "ai-readiness-assessment.json"
    assert ARTIFACT_SCHEMA_ID == "codestrata.ai_readiness_assessment"


def test_taxonomy_is_deterministic_and_namespaced() -> None:
    assert AiReadinessCategory.API_AND_SERVICE_BOUNDARIES.value == (
        "ai_readiness.api_and_service_boundaries"
    )
    assert AiReadinessCategory.UNKNOWN.value == "ai_readiness.unknown"
    assert AI_READINESS_CATEGORIES == tuple(AiReadinessCategory)
    assert all(item.value.startswith("ai_readiness.") for item in AI_READINESS_CATEGORIES)
    values = [item.value for item in AI_READINESS_CATEGORIES]
    assert len(values) == len(set(values))
    joined = " ".join(values)
    assert "readiness score" not in joined
    assert "risk rating" not in joined
    assert "compliance grade" not in joined


def test_coerce_unknown_taxonomy_values() -> None:
    assert (
        coerce_ai_readiness_category("ai_readiness.rag_enabling_assets")
        is AiReadinessCategory.RAG_ENABLING_ASSETS
    )
    assert (
        coerce_ai_readiness_category("rag_enabling_assets")
        is AiReadinessCategory.RAG_ENABLING_ASSETS
    )
    assert (
        coerce_ai_readiness_category("ai_readiness.tool-and-mcp-integration")
        is AiReadinessCategory.TOOL_AND_MCP_INTEGRATION
    )
    assert coerce_ai_readiness_category("not-a-real-category") is AiReadinessCategory.UNKNOWN
    assert coerce_ai_readiness_category("") is AiReadinessCategory.UNKNOWN
    assert coerce_ai_readiness_category(None) is AiReadinessCategory.UNKNOWN


def test_finding_category_ai_readiness_mapping() -> None:
    assert FindingCategory.AI_READINESS.value == "ai_readiness"
    assert RuleCategory.AI_READINESS.value == "ai_readiness"
    assert _CATEGORY_MAP[RuleCategory.AI_READINESS] is FindingCategory.AI_READINESS


def test_deterministic_identifiers() -> None:
    left = build_assessment_id(
        repository_id="repo:demo",
        status="succeeded",
        configuration_fingerprint="abc123",
    )
    right = build_assessment_id(
        repository_id="repo:demo",
        status="succeeded",
        configuration_fingerprint="abc123",
    )
    assert left == right
    assert left.startswith("ai-readiness-assessment:")
    assert build_limitation_id(category="foundation-only", summary="x").startswith(
        "ai-readiness-limitation:"
    )
    assert build_diagnostic_id(code="c", message="m").startswith("ai-readiness-diagnostic:")
    assert build_trace_edge_id(
        relation="section_to_pack",
        source_id="a",
        target_id="b",
    ).startswith("ai-readiness-trace:")


def test_section_forbids_deferred_analysis_fields() -> None:
    fields = AiReadinessAssessmentSection.model_fields
    forbidden = {
        "hotspots",
        "inventories",
        "ai_readiness_score",
        "readiness_score",
        "risk_rating",
        "compliance_grade",
    }
    assert forbidden.isdisjoint(fields.keys())
    assert "finding_inventory" in fields
    assert "capability_family_inventory" in fields
    assert "synthesis" in fields
    assert "themes" in fields
    assert "conclusions" in fields
    assert "recommendations" in fields


def test_empty_section_round_trip_deterministic() -> None:
    left = AiReadinessAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    right = AiReadinessAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = AiReadinessAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.schema_name == SCHEMA_NAME
    assert restored.section_version == "1.2.0"
    assert restored.status.value == "succeeded"
    assert restored.finding_ids == ()
    assert restored.finding_inventory.finding_count == 0
    assert restored.capability_family_inventory.families_total == 7
    assert restored.execution_summary.ai_readiness_rules_planned == 17
    assert restored.execution_summary.rules_executed == 0
    assert "no_ai_readiness_findings" in restored.diagnostics
    assert restored.limitations
