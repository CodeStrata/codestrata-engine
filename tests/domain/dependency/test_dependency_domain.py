"""Dependency Intelligence domain foundation tests (Phase 4.4.1)."""

from __future__ import annotations

from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.domain.dependency.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    DEPENDENCY_ASSESSMENT_FILENAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.dependency.assessment.models import DependencyAssessmentSection
from codestrata.domain.dependency.ids import PACK_ID, PACK_VERSION, RULE_ID_PREFIX
from codestrata.domain.dependency.taxonomy import (
    DEPENDENCY_ROLES,
    DependencyRole,
    coerce_dependency_role,
)
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.enums import RuleCategory
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "dependency.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "dependency."
    assert SECTION_ID == "assessment.dependency"
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert DEPENDENCY_ASSESSMENT_FILENAME == "dependency-assessment.json"
    assert ARTIFACT_SCHEMA_ID == "codestrata.dependency_assessment"


def test_taxonomy_is_deterministic_and_namespaced() -> None:
    assert DependencyRole.RUNTIME_FRAMEWORK.value == "dependency.runtime_framework"
    assert DependencyRole.UNKNOWN.value == "dependency.unknown"
    assert DEPENDENCY_ROLES == tuple(DependencyRole)
    assert all(role.value.startswith("dependency.") for role in DEPENDENCY_ROLES)
    # No package-manager terminology in taxonomy values.
    joined = " ".join(role.value for role in DEPENDENCY_ROLES)
    assert "maven" not in joined
    assert "gradle" not in joined
    assert "npm" not in joined
    assert "pip" not in joined


def test_coerce_unknown_taxonomy_values() -> None:
    assert coerce_dependency_role("dependency.logging") is DependencyRole.LOGGING
    assert coerce_dependency_role("logging") is DependencyRole.LOGGING
    assert coerce_dependency_role("not-a-real-role") is DependencyRole.UNKNOWN
    assert coerce_dependency_role("") is DependencyRole.UNKNOWN
    assert coerce_dependency_role(None) is DependencyRole.UNKNOWN
    assert coerce_dependency_role(DependencyRole.CLOUD_SDK) is DependencyRole.CLOUD_SDK


def test_finding_category_dependency_mapping() -> None:
    assert FindingCategory.DEPENDENCY.value == "dependency"
    assert RuleCategory.DEPENDENCY.value == "dependency"
    assert _CATEGORY_MAP[RuleCategory.DEPENDENCY] is FindingCategory.DEPENDENCY


def test_section_forbids_speculative_fields() -> None:
    fields = DependencyAssessmentSection.model_fields
    forbidden = {
        "frameworks",
        "dependency_inventory",
        "versions",
        "upgrade_candidates",
        "vulnerabilities",
        "licenses",
        "cves",
        "financial_cost",
        "effort_hours",
        "dependency_health_score",
        "priority_score",
    }
    assert forbidden.isdisjoint(fields.keys())
    # Synthesis fields are present as of 4.4.5.
    assert "themes" in fields
    assert "conclusions" in fields
    assert "recommendations" in fields
    assert "synthesis" in fields


def test_empty_section_round_trip_deterministic() -> None:
    from codestrata.application.dependency.assessment.assembler import (
        DependencyAssessmentAssembler,
    )

    left = DependencyAssessmentAssembler().assemble_empty(
        repository_id="repo:codestrata"
    )
    right = DependencyAssessmentAssembler().assemble_empty(
        repository_id="repo:codestrata"
    )
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = DependencyAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.finding_ids == ()
    assert restored.business_impact == "unknown"
    assert "cve-data-not-assessed" in payload
    assert '"vulnerabilities"' not in payload
    assert '"licenses"' not in payload
    assert '"upgrade_candidates"' not in payload
