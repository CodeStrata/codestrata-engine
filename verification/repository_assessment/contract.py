"""Contract for SV.4 repository assessment verification."""

from __future__ import annotations

from dataclasses import dataclass, field

REPOSITORY_ASSESSMENT_VERIFICATION_ID = "repository-assessment-verification"
REPOSITORY_ASSESSMENT_VERIFICATION_VERSION = "1.0.0"

# Permanent catalog — single source of truth (monorepo-relative).
CATALOG_RELATIVE_PATH = "validation/repository-catalog/catalog.json"
CATALOG_SCHEMA_NAME = "codestrata-repository-catalog"

# Canonical Community assessment entry point (scan is legacy).
CANONICAL_ASSESS_COMMAND = ("assess",)
CANONICAL_ASSESS_ARGS = ("--repo", ".", "--output", "reports", "--no-ai")
LEGACY_SCAN_COMMAND = ("scan",)

REQUIRED_ARTIFACT_NAMES: tuple[str, ...] = (
    "report.json",
    "findings.json",
    "recommendations.json",
    "report.html",
)

OPTIONAL_ARTIFACT_HINTS: tuple[str, ...] = (
    "graphs/",
    "security-assessment.json",
    "dependency-assessment.json",
    "technical-debt-assessment.json",
    "testing-assessment.json",
)

FORBIDDEN_SOURCE_MUTATIONS: tuple[str, ...] = (
    "node_modules",
    ".venv",
    "venv",
    "target",
    "dist",
    "build",
)

SCENARIO_IDS: tuple[str, ...] = (
    "A_qualified_catalog_repository",
    "B_controlled_local_fixture",
    "C_path_with_spaces",
    "D_nested_invocation",
    "E_empty_repository",
    "F_unsupported_repository",
    "G_malformed_configuration",
    "H_missing_configuration",
    "I_invalid_output_directory",
    "J_existing_output_artifacts",
    "K_failed_assessment_safety",
    "L_non_interactive",
    "M_offline_deterministic",
    "N_repeat_run_determinism",
)


@dataclass(frozen=True, slots=True)
class AssessmentVerificationContract:
    verification_id: str = REPOSITORY_ASSESSMENT_VERIFICATION_ID
    verification_version: str = REPOSITORY_ASSESSMENT_VERIFICATION_VERSION
    catalog_relative_path: str = CATALOG_RELATIVE_PATH
    canonical_command: tuple[str, ...] = CANONICAL_ASSESS_COMMAND
    canonical_args: tuple[str, ...] = CANONICAL_ASSESS_ARGS
    legacy_command: tuple[str, ...] = LEGACY_SCAN_COMMAND
    required_artifacts: tuple[str, ...] = REQUIRED_ARTIFACT_NAMES
    assessment_schema_version: str = "1.2"
    ai_enabled: bool = False
    telemetry_enabled: bool = False
    network_after_clone: bool = False
    install_repo_dependencies: bool = False
    build_repository: bool = False
    run_repository_tests: bool = False
    scenario_ids: tuple[str, ...] = SCENARIO_IDS
    local_fixture_relative: str = "test-fixtures/sample-js-app"
    notes: tuple[str, ...] = (
        "Canonical customer command is codestrata assess (scan is legacy).",
        "Deterministic mode uses --no-ai; no provider credentials required.",
        "Catalog remote runs require qualified_revision commit or tag.",
        "Clones must remain outside the CodeStrata source tree.",
        "SV.5 owns report content/quality review; SV.4 is structural/workflow only.",
    )
    selection_policy: tuple[str, ...] = (
        "enabled_for.smoke == true",
        "qualified_revision present (commit or tag)",
        "candidate_category prefers Small",
        "supported language_group preferred",
        "lexicographically smallest repository id as tie-breaker",
    )


def default_contract() -> AssessmentVerificationContract:
    return AssessmentVerificationContract()


def duration_bucket(seconds: float) -> str:
    if seconds < 10:
        return "under_10s"
    if seconds < 30:
        return "10s_to_30s"
    if seconds < 120:
        return "30s_to_2m"
    if seconds < 600:
        return "2m_to_10m"
    return "over_10m"
