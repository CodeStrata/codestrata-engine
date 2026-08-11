"""Contract constants for SV.10 curated repository validation."""

from __future__ import annotations

from dataclasses import dataclass

from verification.curated_repository_validation import (
    CURATED_REPOSITORY_VALIDATION_ID,
    CURATED_REPOSITORY_VALIDATION_VERSION,
)
from verification.repository_assessment.contract import (
    CATALOG_RELATIVE_PATH,
    CATALOG_SCHEMA_NAME,
    REQUIRED_ARTIFACT_NAMES,
)

SCHEMA_NAME = "curated-repository-validation"
SCHEMA_VERSION = "1.0.0"
ASSESSMENT_SCHEMA_VERSION = "1.2"
RELEASE_VALIDATION_TARGET = 22

TIER_ORDER: tuple[str, ...] = ("tier1", "tier2", "tier3", "tier4")

# Bounded assessment timeouts (seconds) by catalog tier.
ASSESSMENT_TIMEOUT_S: dict[str, float] = {
    "tier1": 5 * 60,
    "tier2": 15 * 60,
    "tier3": 20 * 60,
    "tier4": 30 * 60,
}

# Clone/fetch timeouts (seconds). Tier 4 repos can be very large.
CLONE_TIMEOUT_S: dict[str, float] = {
    "tier1": 5 * 60,
    "tier2": 10 * 60,
    "tier3": 15 * 60,
    "tier4": 30 * 60,
}

FAILURE_CLASSIFICATIONS: tuple[str, ...] = (
    "clone_failure",
    "revision_mismatch",
    "initialization_failure",
    "doctor_failure",
    "assessment_failure",
    "timeout",
    "artifact_missing",
    "artifact_malformed",
    "schema_failure",
    "traceability_failure",
    "source_integrity_failure",
    "determinism_failure",
    "privacy_failure",
    "unsupported_repository_behavior",
    "infrastructure_or_harness_failure",
)

DATASET_DISCLAIMER = (
    "Results describe only the 22 curated pinned repositories in the v0.2.0 "
    "release-validation catalog and are not a product-wide accuracy claim."
)


@dataclass(frozen=True, slots=True)
class CuratedValidationContract:
    verification_id: str = CURATED_REPOSITORY_VALIDATION_ID
    verification_version: str = CURATED_REPOSITORY_VALIDATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    catalog_relative_path: str = CATALOG_RELATIVE_PATH
    catalog_schema_name: str = CATALOG_SCHEMA_NAME
    target_repository_count: int = RELEASE_VALIDATION_TARGET
    assessment_schema_version: str = ASSESSMENT_SCHEMA_VERSION
    required_artifacts: tuple[str, ...] = REQUIRED_ARTIFACT_NAMES
    tier_order: tuple[str, ...] = TIER_ORDER
    ai_enabled: bool = False
    telemetry_enabled: bool = False
    install_repo_dependencies: bool = False
    build_repository: bool = False
    run_repository_tests: bool = False
    initialize_submodules: bool = False
    download_git_lfs: bool = False
    notes: tuple[str, ...] = (
        DATASET_DISCLAIMER,
        "Canonical command: codestrata assess --repo . --output reports --no-ai",
        "Network after clone is blocked for dependency installs, AI, and telemetry.",
        "Submodules and Git LFS are not fetched.",
    )


def default_contract() -> CuratedValidationContract:
    return CuratedValidationContract()
