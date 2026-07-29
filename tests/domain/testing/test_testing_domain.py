"""Test Intelligence domain foundation tests (Phase 4.6.1)."""

from __future__ import annotations

from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.application.testing.assessment.assembler import TestAssessmentAssembler
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.testing.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    TESTING_ASSESSMENT_FILENAME,
    build_assessment_id,
    build_diagnostic_id,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.testing.assessment.models import TestAssessmentSection
from codestrata.domain.testing.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    PACK_VERSION,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_ID_PREFIX,
    RULE_OBSERVED_WITHOUT_DECLARATION,
    RULE_UNCONFIRMED_CANDIDATES,
    TESTING_RULE_IDS,
)
from codestrata.domain.testing.taxonomy import (
    TEST_CATEGORIES,
    TestCategory,
    coerce_test_category,
)
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "testing.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "testing."
    assert TESTING_RULE_IDS == HYGIENE_RULE_IDS
    assert HYGIENE_RULE_IDS == (
        RULE_DISABLED_OR_SKIPPED,
        RULE_UNCONFIRMED_CANDIDATES,
        RULE_DECLARED_WITHOUT_OBSERVATION,
        RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    )
    assert RULE_OBSERVED_WITHOUT_DECLARATION not in HYGIENE_RULE_IDS
    assert DEFERRED_RULE_IDS == (RULE_OBSERVED_WITHOUT_DECLARATION,)
    assert SECTION_ID == "assessment.testing"
    assert SCHEMA_NAME == "testing-assessment"
    # Additive inventory (1.1) + synthesis (1.2); current contract is 1.2.0.
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert TESTING_ASSESSMENT_FILENAME == "testing-assessment.json"
    assert ARTIFACT_SCHEMA_ID == "codestrata.testing_assessment"


def test_taxonomy_is_deterministic_and_namespaced() -> None:
    assert TestCategory.UNIT_TESTING.value == "testing.unit_testing"
    assert TestCategory.UNKNOWN.value == "testing.unknown"
    assert TEST_CATEGORIES == tuple(TestCategory)
    assert all(item.value.startswith("testing.") for item in TEST_CATEGORIES)
    values = [item.value for item in TEST_CATEGORIES]
    assert len(values) == len(set(values))
    joined = " ".join(values)
    assert "defect probability" not in joined
    assert "mutation score" not in joined
    assert "quality grade" not in joined
    assert "risk rating" not in joined


def test_coerce_unknown_taxonomy_values() -> None:
    assert coerce_test_category("testing.framework") is TestCategory.FRAMEWORK
    assert coerce_test_category("framework") is TestCategory.FRAMEWORK
    assert coerce_test_category("not-a-real-category") is TestCategory.UNKNOWN
    assert coerce_test_category("") is TestCategory.UNKNOWN
    assert coerce_test_category(None) is TestCategory.UNKNOWN
    assert (
        coerce_test_category(TestCategory.MODERNIZATION_SAFETY_NET)
        is TestCategory.MODERNIZATION_SAFETY_NET
    )


def test_finding_category_testing_mapping() -> None:
    assert FindingCategory.TESTING.value == "testing"
    assert RuleCategory.TESTING.value == "testing"
    assert _CATEGORY_MAP[RuleCategory.TESTING] is FindingCategory.TESTING
    # Existing mappings unchanged.
    assert _CATEGORY_MAP[RuleCategory.SECURITY] is FindingCategory.SECURITY
    assert _CATEGORY_MAP[RuleCategory.DEPENDENCY] is FindingCategory.DEPENDENCY
    assert _CATEGORY_MAP[RuleCategory.ARCHITECTURE] is FindingCategory.ARCHITECTURE
    assert _CATEGORY_MAP[RuleCategory.TECHNICAL_DEBT] is FindingCategory.TECHNICAL_DEBT


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
    assert left.startswith("test-assessment:")
    assert build_limitation_id(category="x", summary="y").startswith(
        "test-limitation:"
    )
    assert build_diagnostic_id(code="a", message="b").startswith("test-diagnostic:")
    assert build_trace_edge_id(
        relation="section_to_pack", source_id="a", target_id="b"
    ).startswith("test-trace:")
    assert "uuid" not in left
    assert "/Users/" not in left


def test_section_forbids_analysis_fields() -> None:
    """Schema 1.2.0 allows inventory + synthesis fields; forbid scoring claims."""

    fields = TestAssessmentSection.model_fields
    # Intentional in 1.2.0: synthesis, themes, conclusions, recommendations,
    # inventories (finding_inventory / rule_inventory / …).
    forbidden = {
        "hotspots",
        "coverage_score",
        "test_score",
        "mutation_score",
        "release_readiness",
        "quality_grade",
        "risk_rating",
    }
    assert forbidden.isdisjoint(fields.keys())
    for allowed in (
        "synthesis",
        "themes",
        "conclusions",
        "recommendations",
        "finding_inventory",
        "rule_inventory",
    ):
        assert allowed in fields


def test_empty_section_round_trip_deterministic() -> None:
    left = TestAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    right = TestAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = TestAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.schema_name == SCHEMA_NAME
    assert restored.section_version == SECTION_SCHEMA_VERSION
    assert restored.finding_ids == ()
    assert restored.all_finding_ids == ()
    assert restored.findings == ()
    assert "foundation" in payload.lower()
    assert "test quality" in payload.lower() or "release ready" in payload.lower()
    assert "well tested" not in payload.lower() or "does not establish" in payload.lower()
    assert '"coverage_score"' not in payload
    assert "/Users/" not in payload
