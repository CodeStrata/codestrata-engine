"""Performance Intelligence domain foundation tests (Phase 4.9.1)."""

from __future__ import annotations

from codestrata.application.performance.assessment.assembler import PerformanceAssessmentAssembler
from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.performance.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    PERFORMANCE_ASSESSMENT_FILENAME,
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    build_assessment_id,
    build_diagnostic_id,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.performance.assessment.models import PerformanceAssessmentSection
from codestrata.domain.performance.ids import (
    HYGIENE_RULE_IDS,
    PACK_ID,
    PACK_VERSION,
    PERFORMANCE_RULE_IDS,
    RULE_ALIAS_TO_ID,
    RULE_ID_PREFIX,
)
from codestrata.domain.performance.synthesis.enums import PerformanceSynthesisStatus
from codestrata.domain.performance.taxonomy import (
    PERFORMANCE_CATEGORIES,
    PerformanceCategory,
    coerce_performance_category,
)
from codestrata.domain.rules.enums import RuleCategory
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "performance.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "performance."
    assert len(HYGIENE_RULE_IDS) == 20
    assert PERFORMANCE_RULE_IDS == HYGIENE_RULE_IDS
    assert RULE_ALIAS_TO_ID["PERF-001"] == "performance.perf-001"
    assert RULE_ALIAS_TO_ID["PERF-072"] == "performance.perf-072"
    assert SECTION_ID == "assessment.performance"
    assert SCHEMA_NAME == "performance-assessment"
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert PERFORMANCE_ASSESSMENT_FILENAME == "performance-assessment.json"
    assert ARTIFACT_SCHEMA_ID == "codestrata.performance_assessment"


def test_taxonomy_is_deterministic_and_namespaced() -> None:
    assert PerformanceCategory.INEFFICIENT_DATA_ACCESS.value == (
        "performance.inefficient_data_access"
    )
    assert PerformanceCategory.BLOCKING_OPERATIONS.value == ("performance.blocking_operations")
    assert PerformanceCategory.UNKNOWN.value == "performance.unknown"
    assert PERFORMANCE_CATEGORIES == tuple(PerformanceCategory)
    assert all(item.value.startswith("performance.") for item in PERFORMANCE_CATEGORIES)
    values = [item.value for item in PERFORMANCE_CATEGORIES]
    assert len(values) == len(set(values))
    joined = " ".join(values)
    assert "performance score" not in joined
    assert "latency score" not in joined
    assert "throughput grade" not in joined


def test_coerce_unknown_taxonomy_values() -> None:
    assert coerce_performance_category("performance.caching") is PerformanceCategory.CACHING
    assert coerce_performance_category("caching") is PerformanceCategory.CACHING
    assert (
        coerce_performance_category("performance.blocking-operations")
        is PerformanceCategory.BLOCKING_OPERATIONS
    )
    assert (
        coerce_performance_category("query_patterns") is PerformanceCategory.INEFFICIENT_DATA_ACCESS
    )
    assert (
        coerce_performance_category("performance.query_patterns")
        is PerformanceCategory.INEFFICIENT_DATA_ACCESS
    )
    assert coerce_performance_category("not-a-real-category") is PerformanceCategory.UNKNOWN
    assert coerce_performance_category("") is PerformanceCategory.UNKNOWN
    assert coerce_performance_category(None) is PerformanceCategory.UNKNOWN


def test_finding_category_performance_mapping() -> None:
    assert FindingCategory.PERFORMANCE.value == "performance"
    assert RuleCategory.PERFORMANCE.value == "performance"
    assert _CATEGORY_MAP[RuleCategory.PERFORMANCE] is FindingCategory.PERFORMANCE


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
    assert left.startswith("performance-assessment:")
    assert build_limitation_id(category="foundation-only", summary="x").startswith(
        "performance-limitation:"
    )
    assert build_diagnostic_id(code="c", message="m").startswith("performance-diagnostic:")
    assert build_trace_edge_id(
        relation="section_to_pack",
        source_id="a",
        target_id="b",
    ).startswith("performance-trace:")


def test_section_forbids_deferred_analysis_fields() -> None:
    fields = PerformanceAssessmentSection.model_fields
    forbidden = {
        "hotspots",
        "performance_score",
        "latency_score",
        "throughput_grade",
        "risk_rating",
        "compliance_grade",
    }
    assert forbidden.isdisjoint(fields.keys())
    assert "finding_inventory" in fields
    assert "performance_family_inventory" in fields
    assert "synthesis" in fields
    assert "themes" in fields
    assert "conclusions" in fields
    assert "recommendations" in fields


def test_empty_section_round_trip_deterministic() -> None:
    left = PerformanceAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    right = PerformanceAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = PerformanceAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.schema_name == SCHEMA_NAME
    assert restored.section_version == "1.2.0"
    assert restored.status.value == "succeeded"
    assert restored.finding_ids == ()
    assert restored.findings == ()
    assert restored.finding_inventory.finding_count == 0
    assert restored.performance_family_inventory.families_total == 8
    assert restored.performance_family_inventory.families_observed == 0
    assert restored.execution_summary.performance_rules_planned == 20
    assert restored.execution_summary.rules_executed == 0
    assert restored.synthesis.status is PerformanceSynthesisStatus.NOT_REQUESTED
    assert restored.synthesis.themes == ()
    assert restored.themes == ()
    assert restored.conclusions == ()
    assert restored.recommendations == ()
