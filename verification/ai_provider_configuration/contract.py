"""Contract constants for SV.11.3 Standardized Provider and Model Configuration verification.

CodeStrata v0.2.0 Epic 11, Slice 11.3. This package verifies the **new,
unwired** ``codestrata.ai.provider_contracts.configuration_*`` (plus
``adapter_configuration.py``/``legacy_configuration.py``/
``model_configuration.py``) domain modules: their dependency boundary, their
bounded value objects, their compatibility with the Slice 11.1 baseline
(CR-1..CR-6), provider/model resolution correctness, credential-requirement
shape, adapter type safety, privacy, and determinism. It does not run, and
does not require, any real provider network access or credentials, and it
never reads ``os.environ`` or a file on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from verification.ai_provider_contracts.contract import (
    EXPECTED_MODULES as SLICE_11_2_MODULES,
)

VERIFICATION_ID = "ai-provider-configuration-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "ai-provider-configuration-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.3"
SLICE_TITLE = "Standardized Provider and Model Configuration"

PACKAGE_DOTTED_NAME = "codestrata.ai.provider_contracts"
PACKAGE_RELATIVE_PATH = "ai/provider_contracts"

# The 12 modules Slice 11.3 adds to the existing (Slice 11.2) package.
SLICE_11_3_NEW_MODULES: tuple[str, ...] = (
    "adapter_configuration.py",
    "configuration_compatibility.py",
    "configuration_diagnostics.py",
    "configuration_models.py",
    "configuration_policy.py",
    "configuration_precedence.py",
    "configuration_projection.py",
    "configuration_serialization.py",
    "configuration_sources.py",
    "configuration_validation.py",
    "legacy_configuration.py",
    "model_configuration.py",
)

# The full expected module set for the package after Slice 11.3 (Slice 11.2's
# set plus Slice 11.3's additions). Used to confirm nothing from either slice
# went missing and nothing unexpected was added.
EXPECTED_MODULES: tuple[str, ...] = tuple(
    sorted(set(SLICE_11_2_MODULES) | set(SLICE_11_3_NEW_MODULES))
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

# The Slice 11.3 configuration modules must never import os/pathlib/subprocess
# — every resolution function takes already-extracted plain values, never
# reading the environment or a file itself.
FORBIDDEN_ENVIRONMENT_IMPORT_MODULES: tuple[str, ...] = ("os", "pathlib", "subprocess")

# Product-path files that must never import any provider_contracts module —
# extended (relative to Slice 11.2's list) with doctor.py, aws_config.py,
# the config layer, and the assess CLI, since Slice 11.3 explicitly targets
# "no product-path imports of new configuration modules from assess factory,
# providers, enrichment, doctor, CLI."
#
# Slice 11.6 migrated OpenAI and Slice 11.7 migrated Bedrock onto the
# contracts, so ``ai/providers/openai_provider.py`` and
# ``ai/providers/bedrock.py`` (now compatibility wrappers) and the
# ``ai/provider_adapters/`` package are deliberately absent from this list;
# SV.11.6/SV.11.7 assert the positive direction for them instead.
# ``ai/aws_config.py`` stays: it remains the SDK/credential boundary and
# still must not import the contracts.
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

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "configuration_not_wired",
    "providers_not_migrated",
    "credential_resolution_deferred",
    "timeout_retry_execution_deferred",
)

REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

# Ground-truth defaults this slice must never change (see
# engine/docs/ai-provider-configuration.md and the loaded Slice 11.1
# baseline for the real, enforced source of truth).
DEFAULT_PROVIDER_ID = "bedrock"
DEFAULT_MODEL_IDS: dict[str, str] = {
    "bedrock": "amazon.nova-lite-v1:0",
    "openai": "gpt-4o-mini",
}

OUTPUT_RELATIVE = "reports/verification/sv11-3"
REPORT_FILENAME = "ai-provider-configuration-verification.json"
REPORT_MD_FILENAME = "ai-provider-configuration-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 20

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")


@dataclass(frozen=True, slots=True)
class ConfigurationVerificationContract:
    """Pass/fail contract for SV.11.3 Standardized Provider and Model Configuration verification."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    required_compatibility_requirement_ids: tuple[str, ...] = REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    default_provider_id: str = DEFAULT_PROVIDER_ID
    start_slice_11_4: bool = False
    migrate_openai_or_bedrock: bool = False
    add_openrouter: bool = False
    wire_configuration_into_assessment_product_path: bool = False
    wire_configuration_to_ai_provider_protocol: bool = False
    modify_provider_selection_defaults_or_model_resolution_defaults: bool = False
    modify_precedence_or_config_keys: bool = False
    wire_timeout_or_retry: bool = False
    modify_doctor_cli_or_execution: bool = False
    modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.3 verifies the new configuration_* domain modules: bounded value objects, "
            "dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, provider/model "
            "resolution correctness, privacy, and determinism.",
            "PASS_WITH_LIMITATIONS is expected: configuration_not_wired, "
            "providers_not_migrated, credential_resolution_deferred, and "
            "timeout_retry_execution_deferred are recorded, intentional limitations.",
        )
    )


def default_contract() -> ConfigurationVerificationContract:
    return ConfigurationVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "DEFAULT_MODEL_IDS",
    "DEFAULT_PROVIDER_ID",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MODULES",
    "FORBIDDEN_ENVIRONMENT_IMPORT_MODULES",
    "FORBIDDEN_IMPORT_PREFIXES",
    "FORBIDDEN_PROVIDER_TOKENS",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OUTPUT_RELATIVE",
    "PACKAGE_DOTTED_NAME",
    "PACKAGE_RELATIVE_PATH",
    "PRODUCT_PATH_FILES",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SLICE_11_2_MODULES",
    "SLICE_11_3_NEW_MODULES",
    "SLICE_ID",
    "SLICE_TITLE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "ConfigurationVerificationContract",
    "default_contract",
]
