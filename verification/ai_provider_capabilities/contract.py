"""Contract constants for SV.11.5 Provider Usage Metadata and Capability Discovery verification.

CodeStrata v0.2.0 Epic 11, Slice 11.5. This package verifies the **new,
unwired** ``codestrata.ai.provider_contracts.capability_*``/``usage_*``
domain modules (plus the in-place extension of ``usage.py`` with an optional
``completion_status`` field): their dependency boundary, their bounded value
objects, the two static baseline capability catalogs (bedrock, openai),
their compatibility with the Slice 11.1 baseline (CR-1..CR-6) and with
Slices 11.2/11.3/11.4, their privacy properties, and their determinism. It
does not run, and does not require, any real provider network access or
credentials, and it never reads ``os.environ`` or a file on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from verification.ai_provider_execution.contract import EXPECTED_MODULES as SLICE_11_4_MODULES

VERIFICATION_ID = "ai-provider-capability-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "ai-provider-capability-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.5"
SLICE_TITLE = "Provider Usage Metadata and Capability Discovery"

PACKAGE_DOTTED_NAME = "codestrata.ai.provider_contracts"
PACKAGE_RELATIVE_PATH = "ai/provider_contracts"

# The 12 modules Slice 11.5 adds to the existing (Slice 11.2 + 11.3 + 11.4)
# package. usage.py itself is extended in place (an optional
# completion_status field) and is therefore NOT listed here — it is already
# part of SLICE_11_4_MODULES (inherited from Slice 11.2).
SLICE_11_5_NEW_MODULES: tuple[str, ...] = (
    "capability_catalogs.py",
    "capability_compatibility.py",
    "capability_diagnostics.py",
    "capability_models.py",
    "capability_policy.py",
    "capability_schema.py",
    "capability_serialization.py",
    "capability_validation.py",
    "usage_diagnostics.py",
    "usage_policy.py",
    "usage_serialization.py",
    "usage_validation.py",
)

# The full expected module set for the package after Slice 11.5 (Slice
# 11.2+11.3+11.4's set plus Slice 11.5's additions). Used to confirm nothing
# from any prior slice went missing and nothing unexpected was added.
EXPECTED_MODULES: tuple[str, ...] = tuple(
    sorted(set(SLICE_11_4_MODULES) | set(SLICE_11_5_NEW_MODULES))
)

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "openai",
    "boto3",
    "botocore",
    "httpx",
    "requests",
    "codestrata.platform",
    "codestrata.datalake",
    "codestrata.telemetry",
    "codestrata.analytics",
    "codestrata.cli",
    "codestrata.reporting",
)

# The Slice 11.5 capability_*/usage_* modules must never import
# os/pathlib/subprocess/threading/asyncio/signal — none of them reads the
# environment or a file itself, and none makes a network call.
FORBIDDEN_ENVIRONMENT_IMPORT_MODULES: tuple[str, ...] = (
    "os",
    "pathlib",
    "subprocess",
    "threading",
    "asyncio",
    "signal",
)

# Product-path files that must never import any provider_contracts module —
# identical to the Slice 11.3/11.4 list (Slice 11.5 does not widen the set
# of files that must remain free of provider_contracts imports), minus the
# OpenAI files that Slice 11.6 migrated and the Bedrock file that Slice 11.7
# migrated onto the contracts. SV.11.6/SV.11.7 assert the positive direction
# for ``ai/providers/openai_provider.py``, ``ai/providers/bedrock.py``, and
# ``ai/provider_adapters/``; orchestration and ``ai/aws_config.py`` stay
# contract-free here.
PRODUCT_PATH_FILES: tuple[str, ...] = (
    "application/assessment/service.py",
    "ai/enrichment/service.py",
    "ai/providers/__init__.py",
    "ai/providers/factory.py",
    "ai/providers/doctor.py",
    "ai/aws_config.py",
    "extensions/assess_ai.py",
    "config/settings.py",
    "config/profiles.py",
    "cli/assess.py",
)

FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = ("openrouter", "OpenRouter", "OPENROUTER")

# Engine provider IDs a capability profile is allowed to describe. This is
# the exact set covered by capability_catalogs.py's static baseline.
KNOWN_CAPABILITY_PROVIDER_IDS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

# The bounded completion-status vocabulary ProviderUsageMetadata.
# completion_status is allowed to carry, aligned with
# execution.ProviderExecutionStatus (Slice 11.4).
ALLOWED_USAGE_COMPLETION_STATUSES: tuple[str, ...] = (
    "success",
    "unavailable",
    "failed",
    "skipped",
)

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "provider_capabilities_not_consumed",
    "usage_metadata_not_wired",
    "providers_not_migrated",
    "openrouter_operational_explicit",
    "openrouter_doctor_local_readiness_only",
)

REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

# Prior slices this slice must not modify (checked via cross-slice
# compatibility statements loaded from codestrata.ai.provider_contracts.
# capability_compatibility.build_prior_slice_compatibility_notes()).
PRIOR_SLICE_IDS: tuple[str, ...] = ("11.2", "11.3", "11.4")

OUTPUT_RELATIVE = "reports/verification/sv11-5"
REPORT_FILENAME = "ai-provider-capability-verification.json"
REPORT_MD_FILENAME = "ai-provider-capability-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 20

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")


@dataclass(frozen=True, slots=True)
class CapabilityVerificationContract:
    """Pass/fail contract for SV.11.5 Provider Usage Metadata and Capability Discovery."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    required_compatibility_requirement_ids: tuple[str, ...] = REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    known_capability_provider_ids: tuple[str, ...] = KNOWN_CAPABILITY_PROVIDER_IDS
    start_slice_11_6: bool = False
    migrate_openai_or_bedrock: bool = False
    add_openrouter: bool = False
    wire_capability_discovery_or_usage_metadata_into_product_path: bool = False
    modify_runtime_provider_behavior: bool = False
    modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.5 verifies the new capability_*/usage_* domain modules: bounded value "
            "objects, dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, Slice "
            "11.2/11.3/11.4 non-interference, the two static baseline capability catalogs, "
            "privacy, and determinism.",
            "PASS_WITH_LIMITATIONS is expected: provider_capabilities_not_consumed, "
            "usage_metadata_not_wired, providers_not_migrated, and "
            "openrouter_operational_explicit and openrouter_doctor_local_readiness_only "
            "are recorded, intentional limitations.",
        )
    )


def default_contract() -> CapabilityVerificationContract:
    return CapabilityVerificationContract()


__all__ = [
    "ALLOWED_USAGE_COMPLETION_STATUSES",
    "ALLOWED_VERDICTS",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MODULES",
    "FORBIDDEN_ENVIRONMENT_IMPORT_MODULES",
    "FORBIDDEN_IMPORT_PREFIXES",
    "FORBIDDEN_PROVIDER_TOKENS",
    "KNOWN_CAPABILITY_PROVIDER_IDS",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OUTPUT_RELATIVE",
    "PACKAGE_DOTTED_NAME",
    "PACKAGE_RELATIVE_PATH",
    "PRIOR_SLICE_IDS",
    "PRODUCT_PATH_FILES",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SLICE_11_4_MODULES",
    "SLICE_11_5_NEW_MODULES",
    "SLICE_ID",
    "SLICE_TITLE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "CapabilityVerificationContract",
    "default_contract",
]
