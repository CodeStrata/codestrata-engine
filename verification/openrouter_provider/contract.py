"""Contract constants for SV.11.9 OpenRouter Provider Implementation verification.

CodeStrata v0.2.0 Epic 11, Slice 11.9 implemented an OpenRouter adapter against
Slice 11.2–11.5 contracts. Slice 11.10 registered OpenRouter in
``AssessAIProviderRegistry`` (explicit-only; Bedrock remains default). Decision B
(Slice 11.8) keeps ``AssessAIProviderRegistry`` authoritative; the common
``AIProviderRegistry`` is still not globally wired. Slice 11.11 added doctor
local readiness for OpenRouter (no client construction or model invoke).
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "openrouter-provider-verification"
VERIFICATION_VERSION = "1.0.0"
SCHEMA_NAME = "openrouter-provider-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.9"
SLICE_TITLE = "OpenRouter Provider Implementation"

ASSESSMENT_SCHEMA_VERSION = "1.2"
PROVIDER_ID = "openrouter"
DEFAULT_ASSESS_PROVIDER = "bedrock"
ASSESS_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
CONTRACT_PROVIDER_IDS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

PACKAGE_RELATIVE_PATH = "ai/provider_adapters/openrouter"
EXPECTED_MODULES: tuple[str, ...] = (
    "__init__.py",
    "adapter.py",
    "capabilities.py",
    "client.py",
    "configuration.py",
    "diagnostics.py",
    "error_mapping.py",
    "factory.py",
    "legacy_bridge.py",
    "request_mapping.py",
    "response_mapping.py",
    "usage_mapping.py",
)

# Test-only synthetic model — never a product default.
TEST_ONLY_MODEL_REFERENCE = "test-only/openrouter-model"

EXPECTED_MAXIMUM_ATTEMPTS = 1

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_openrouter_calls",
    "model_specific_feature_support_not_probed",
    "operational_retry_conservative",
    "openrouter_doctor_local_readiness_only",
)

OUTPUT_RELATIVE = "reports/verification/sv11-9"
REPORT_FILENAME = "openrouter-provider-verification.json"
REPORT_MD_FILENAME = "openrouter-provider-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 26
ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")

COMMON_CONTRACT_VERSION_UNCHANGED = "1.0"
COMMON_CONTRACT_COMPATIBILITY_DECISION = (
    "additive_provider_id_under_contract_1_0_no_version_bump"
)


@dataclass(frozen=True, slots=True)
class OpenRouterProviderVerificationContract:
    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    start_slice_11_10: bool = False
    register_in_assess: bool = True
    add_toml_or_env_auth: bool = False
    modify_doctor_or_cli: bool = False
    change_openai_or_bedrock: bool = False
    change_default_provider: bool = False
    activate_multi_attempt_retries: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.9 proves OpenRouter can implement the provider platform contracts "
            "without redesigning them.",
            f"Common-contract decision: {COMMON_CONTRACT_COMPATIBILITY_DECISION}",
            "Slice 11.10 registered OpenRouter in AssessAIProviderRegistry (explicit-only); "
            "configuration and authentication live in Slice 11.10. Doctor local readiness "
            "landed in Slice 11.11 (no client construction or model invoke).",
            "PASS_WITH_LIMITATIONS expected: no live OpenRouter calls; doctor local "
            "readiness only.",
        )
    )


def default_contract() -> OpenRouterProviderVerificationContract:
    return OpenRouterProviderVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "ASSESSMENT_SCHEMA_VERSION",
    "ASSESS_REGISTERED_PROVIDERS",
    "COMMON_CONTRACT_COMPATIBILITY_DECISION",
    "COMMON_CONTRACT_VERSION_UNCHANGED",
    "CONTRACT_PROVIDER_IDS",
    "DEFAULT_ASSESS_PROVIDER",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "EXPECTED_MODULES",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OUTPUT_RELATIVE",
    "PACKAGE_RELATIVE_PATH",
    "PROVIDER_ID",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SLICE_ID",
    "SLICE_TITLE",
    "TEST_ONLY_MODEL_REFERENCE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "OpenRouterProviderVerificationContract",
    "default_contract",
]
