"""Security Intelligence domain foundation tests (Phase 4.5.1)."""

from __future__ import annotations

from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.security.assessment.identifiers import (
    ARTIFACT_SCHEMA_ID,
    SCHEMA_NAME,
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
    SECURITY_ASSESSMENT_FILENAME,
    build_assessment_id,
    build_diagnostic_id,
    build_limitation_id,
    build_trace_edge_id,
)
from codestrata.domain.security.assessment.models import SecurityAssessmentSection
from codestrata.domain.security.ids import PACK_ID, PACK_VERSION, RULE_ID_PREFIX
from codestrata.domain.security.taxonomy import (
    SECURITY_CATEGORIES,
    SecurityCategory,
    coerce_security_category,
)
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "security.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "security."
    assert SECTION_ID == "assessment.security"
    assert SCHEMA_NAME == "security-assessment"
    assert SECTION_SCHEMA_VERSION == "1.3.0"
    assert SECURITY_ASSESSMENT_FILENAME == "security-assessment.json"
    assert ARTIFACT_SCHEMA_ID == "codestrata.security_assessment"


def test_taxonomy_is_deterministic_and_namespaced() -> None:
    assert SecurityCategory.CREDENTIAL.value == "security.credential"
    assert SecurityCategory.UNKNOWN.value == "security.unknown"
    assert SECURITY_CATEGORIES == tuple(SecurityCategory)
    assert all(item.value.startswith("security.") for item in SECURITY_CATEGORIES)
    joined = " ".join(item.value for item in SECURITY_CATEGORIES)
    assert "owasp" not in joined
    assert "cwe" not in joined
    assert "cve" not in joined
    assert "nist" not in joined


def test_coerce_unknown_taxonomy_values() -> None:
    assert coerce_security_category("security.logging") is SecurityCategory.LOGGING
    assert coerce_security_category("logging") is SecurityCategory.LOGGING
    assert coerce_security_category("not-a-real-category") is SecurityCategory.UNKNOWN
    assert coerce_security_category("") is SecurityCategory.UNKNOWN
    assert coerce_security_category(None) is SecurityCategory.UNKNOWN
    assert (
        coerce_security_category(SecurityCategory.AUTHENTICATION)
        is SecurityCategory.AUTHENTICATION
    )


def test_finding_category_security_mapping() -> None:
    assert FindingCategory.SECURITY.value == "security"
    assert RuleCategory.SECURITY.value == "security"
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
    assert left.startswith("sec-assessment:")
    assert build_limitation_id(category="x", summary="y").startswith("sec-limitation:")
    assert build_diagnostic_id(code="a", message="b").startswith("sec-diagnostic:")
    assert build_trace_edge_id(
        relation="section_to_pack", source_id="a", target_id="b"
    ).startswith("sec-trace:")


def test_section_forbids_speculative_fields() -> None:
    fields = SecurityAssessmentSection.model_fields
    forbidden = {
        "secrets",
        "credentials",
        "vulnerabilities",
        "cves",
        "owasp",
        "cwe",
        "risk_score",
        "security_score",
        "hotspots",
        "financial_cost",
        "effort_hours",
        "cvss",
        "compliance_score",
    }
    assert forbidden.isdisjoint(fields.keys())
    # Synthesis mirrors (themes/conclusions/recommendations) are allowed in 4.5.5.
    assert "themes" in fields
    assert "conclusions" in fields
    assert "recommendations" in fields
    assert "synthesis" in fields


def test_empty_section_round_trip_deterministic() -> None:
    left = SecurityAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    right = SecurityAssessmentAssembler().assemble_empty(repository_id="repo:codestrata")
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = SecurityAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.schema_name == SCHEMA_NAME
    assert restored.section_version == "1.3.0"
    assert restored.finding_ids == ()
    assert restored.finding_summaries == ()
    assert restored.business_impact == "unknown"
    assert "foundation-only" in payload
    assert "rules-not-implemented" in payload
    assert '"vulnerabilities"' not in payload
    assert '"cves"' not in payload
    assert '"owasp"' not in payload
    assert '"risk_score"' not in payload
    assert "/Users/" not in payload
