"""Contract constants for SV.11.2 Common AI Provider Contracts verification.

CodeStrata v0.2.0 Epic 11, Slice 11.2 — Common AI Provider Contracts. This
package verifies the **new, unwired** ``codestrata.ai.provider_contracts``
domain package: its dependency boundary, its bounded value objects, its
compatibility with the Slice 11.1 baseline (CR-1..CR-6), its privacy
properties, and its determinism. It does not run, and does not require, any
real provider network access or credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "ai-provider-contract-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "ai-provider-contract-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.2"
SLICE_TITLE = "Common AI Provider Contracts"

PACKAGE_DOTTED_NAME = "codestrata.ai.provider_contracts"
PACKAGE_RELATIVE_PATH = "ai/provider_contracts"

# The Slice 11.2 module set, as originally shipped by this slice.
SLICE_11_2_MODULES: tuple[str, ...] = (
    "__init__.py",
    "capabilities.py",
    "compatibility.py",
    "diagnostics.py",
    "errors.py",
    "execution.py",
    "identifiers.py",
    "policy.py",
    "provider.py",
    "registry.py",
    "relationship.py",
    "requests.py",
    "responses.py",
    "serialization.py",
    "usage.py",
    "validation.py",
    "versions.py",
)

# Slice 11.3 (Standardized Provider and Model Configuration) later extended
# this same sibling package with 12 configuration_* modules — see
# verification.ai_provider_configuration.contract.SLICE_11_3_MODULES for the
# authoritative list. This inventory check must tolerate their presence
# (they are not "unexpected" files) without this package's own scope
# growing: SV.11.2 verifies only the Slice 11.2 modules' behavior.
SLICE_11_3_MODULES: tuple[str, ...] = (
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

# Slice 11.4 (Standardized Execution, Errors, Timeouts, and Retries) later
# extended this same sibling package with 11 execution_* (plus
# timeout_policy.py/retry_policy.py/retry_decision.py/backoff.py/
# error_classification.py/executor.py) modules — see
# verification.ai_provider_execution.contract.SLICE_11_4_NEW_MODULES for the
# authoritative list. This inventory check must tolerate their presence too,
# for the same reason as Slice 11.3's tolerance above.
SLICE_11_4_MODULES: tuple[str, ...] = (
    "backoff.py",
    "error_classification.py",
    "execution_compatibility.py",
    "execution_diagnostics.py",
    "execution_models.py",
    "execution_policy.py",
    "execution_serialization.py",
    "executor.py",
    "retry_decision.py",
    "retry_policy.py",
    "timeout_policy.py",
)

# Slice 11.5 (Provider Usage Metadata and Capability Discovery) later
# extended this same sibling package with 12 capability_*/usage_* modules
# (usage.py itself is extended in place, not added — it is already listed
# under SLICE_11_2_MODULES) — see
# verification.ai_provider_capabilities.contract.SLICE_11_5_NEW_MODULES for
# the authoritative list. This inventory check must tolerate their presence
# too, for the same reason as Slice 11.3/11.4's tolerance above.
SLICE_11_5_MODULES: tuple[str, ...] = (
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

EXPECTED_MODULES: tuple[str, ...] = tuple(
    sorted(
        {
            *SLICE_11_2_MODULES,
            *SLICE_11_3_MODULES,
            *SLICE_11_4_MODULES,
            *SLICE_11_5_MODULES,
        }
    )
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

# Legacy product-path files that must never import a provider_contracts
# module. Slice 11.6 migrated OpenAI and Slice 11.7 migrated Bedrock onto the
# contracts, so ``ai/providers/openai_provider.py`` and
# ``ai/providers/bedrock.py`` (now compatibility wrappers) and the
# ``ai/provider_adapters/`` package are deliberately absent from this list;
# SV.11.6/SV.11.7 assert the positive direction for them instead. The
# orchestration layers still must not import the contracts.
PRODUCT_PATH_FILES: tuple[str, ...] = (
    "application/assessment/service.py",
    "ai/enrichment/service.py",
    "ai/providers/__init__.py",
    "ai/providers/factory.py",
    "extensions/assess_ai.py",
)

FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = ("openrouter", "OpenRouter", "OPENROUTER")

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "contracts_not_wired_to_runtime",
    "providers_not_migrated",
)

REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

OUTPUT_RELATIVE = "reports/verification/sv11-2"
REPORT_FILENAME = "ai-provider-contract-verification.json"
REPORT_MD_FILENAME = "ai-provider-contract-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 20

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")


@dataclass(frozen=True, slots=True)
class ContractVerificationContract:
    """Pass/fail contract for SV.11.2 Common AI Provider Contracts verification."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    required_compatibility_requirement_ids: tuple[str, ...] = REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    start_slice_11_3: bool = False
    migrate_openai_or_bedrock: bool = False
    add_openrouter: bool = False
    wire_contracts_into_assessment_product_path: bool = False
    modify_provider_selection_defaults_config_model_resolution: bool = False
    modify_timeouts_retries_auth_errors_doctor_or_ai_execution: bool = False
    modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.2 verifies the new codestrata.ai.provider_contracts domain package: "
            "bounded value objects, dependency boundary, Slice 11.1 CR-1..CR-6 compatibility, "
            "privacy, and determinism.",
            "PASS_WITH_LIMITATIONS is expected: contracts_not_wired_to_runtime and "
            "providers_not_migrated are recorded, intentional limitations of this slice.",
        )
    )


def default_contract() -> ContractVerificationContract:
    return ContractVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MODULES",
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
    "SLICE_11_3_MODULES",
    "SLICE_11_4_MODULES",
    "SLICE_11_5_MODULES",
    "SLICE_ID",
    "SLICE_TITLE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "ContractVerificationContract",
    "default_contract",
]
