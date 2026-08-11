"""Contract constants for SV.11 assessment consistency verification."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2.assessment_heads import AssessmentHead
from verification.assessment_consistency import (
    ASSESSMENT_CONSISTENCY_VERIFICATION_ID,
    ASSESSMENT_CONSISTENCY_VERIFICATION_VERSION,
)
from verification.curated_repository_validation.contract import (
    RELEASE_VALIDATION_TARGET,
    SCHEMA_NAME as SV10_SCHEMA_NAME,
)
from verification.repository_assessment.contract import (
    CATALOG_RELATIVE_PATH,
    REQUIRED_ARTIFACT_NAMES,
)

SCHEMA_NAME = "assessment-consistency-verification"
SCHEMA_VERSION = "1.0.0"
ASSESSMENT_SCHEMA_VERSION = ASSESSMENT_JSON_SCHEMA_VERSION  # "1.2"

SV10_OUTPUT_RELATIVE = "reports/verification/sv10"
SV11_OUTPUT_RELATIVE = "reports/verification/sv11"
REPORT_FILENAME = "assessment-consistency-verification.json"

CANONICAL_HEAD_IDS: frozenset[str] = frozenset(h.value for h in AssessmentHead)
# Coverage map may include testing/performance which are capability areas.
COVERAGE_AREA_HEAD_IDS: frozenset[str] = frozenset(
    {
        *CANONICAL_HEAD_IDS,
        "testing",
        "performance",
    }
) - {"engineering_intelligence"}

SEVERITY_VOCAB: frozenset[str] = frozenset(
    {"critical", "high", "medium", "low", "informational", "info"}
)
PRIORITY_VOCAB: frozenset[str] = frozenset(
    {"immediate", "critical", "high", "medium", "low"}
)
CONFIDENCE_LEVEL_VOCAB: frozenset[str] = frozenset(
    {"high", "moderate", "limited", "unavailable"}
)
COVERAGE_STATUS_VOCAB: frozenset[str] = frozenset(
    {
        "complete",
        "partial",
        "insufficient_evidence",
        "unavailable",
        "disabled",
        "not_applicable",
    }
)
ACTIVATION_DECISION_VOCAB: frozenset[str] = frozenset(
    {"enabled", "skipped", "disabled", "not_applicable", "unavailable"}
)
RECOMMENDATION_TYPE_VOCAB: frozenset[str] = frozenset(
    {"finding_backed", "legacy", "fact_based", "fact-based"}
)

# SV.10 repository-scoped limitations that must remain correctly placed.
EXPECTED_LIMITATION_REPOS: dict[str, tuple[str, ...]] = {
    "juice-shop": ("secret-shaped", "intentionally"),
    "nodegoat": ("secret-shaped", "intentionally"),
    "bookstack": ("slower", "laravel", "tier 3"),
    "aspnetcore": ("submodule",),
    "doris": ("submodule",),
}

DEFECT_CLASSIFICATIONS: tuple[str, ...] = (
    "artifact_contract",
    "schema_contract",
    "head_ownership",
    "activation_semantics",
    "coverage_semantics",
    "confidence_semantics",
    "finding_contract",
    "consolidation_contract",
    "correlation_contract",
    "severity_policy",
    "recommendation_authority",
    "priority_policy",
    "traceability",
    "limitation_placement",
    "terminology",
    "privacy",
    "determinism",
    "engineering_intelligence_input",
)

HANDLING_OPTIONS: tuple[str, ...] = (
    "verification_harness_fix",
    "product_defect_for_sv13",
    "repository_specific_limitation",
    "expected_variation",
    "documentation_only",
)

FORBIDDEN_QUALITY_CONCLUSIONS: tuple[str, ...] = (
    "healthier than",
    "more mature",
    "better engineering",
    "maturity score",
    "health score",
    "readiness score",
    "risk score",
    "best repository",
    "worst repository",
    "rank repositories",
    "portfolio recommendation",
)

TERMINOLOGY_FORBIDDEN: tuple[str, ...] = (
    "maturity score",
    "health score",
    "readiness score",
    "risk score",
    "confidence percentage",
    "validation precision",
    "validation recall",
)

# Contract-relevant terminology that should not appear as health claims.
HEALTHY_ZERO_FINDINGS_PATTERNS: tuple[str, ...] = (
    "healthy: zero findings",
    "zero findings means healthy",
    "repository is healthy because",
    "ready because no findings",
)

DATASET_DISCLAIMER = (
    "SV.11 verifies assessment contract consistency across the 22 curated "
    "v0.2.0 release-validation repositories only. It is not an accuracy, "
    "precision/recall, maturity, health, or ranking benchmark."
)

QUALITY_COMPARISON_GUARD = (
    "Cross-repository comparisons evaluate contracts, schemas, vocabularies, "
    "and reference integrity only — never repository quality, maturity, or health."
)


@dataclass(frozen=True, slots=True)
class ConsistencyContract:
    verification_id: str = ASSESSMENT_CONSISTENCY_VERIFICATION_ID
    verification_version: str = ASSESSMENT_CONSISTENCY_VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    catalog_relative_path: str = CATALOG_RELATIVE_PATH
    sv10_schema_name: str = SV10_SCHEMA_NAME
    target_repository_count: int = RELEASE_VALIDATION_TARGET
    assessment_schema_version: str = ASSESSMENT_SCHEMA_VERSION
    required_artifacts: tuple[str, ...] = REQUIRED_ARTIFACT_NAMES
    reassess_by_default: bool = False
    clone_by_default: bool = False
    install_repo_dependencies: bool = False
    build_repository: bool = False
    run_repository_tests: bool = False
    start_sv12: bool = False
    notes: tuple[str, ...] = (
        DATASET_DISCLAIMER,
        QUALITY_COMPARISON_GUARD,
        "Inputs: engine/reports/verification/sv10/ records and preserved artifacts.",
        "No network, clone, or reassessment by default.",
    )


def default_contract() -> ConsistencyContract:
    return ConsistencyContract()
