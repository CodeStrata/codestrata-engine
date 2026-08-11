"""Contract constants for SV.11.8 Cross-Provider Contract Verification.

CodeStrata v0.2.0 Epic 11, Slice 11.8. Slices 11.6 and 11.7 migrated OpenAI
and Bedrock onto the Slice 11.2–11.5 contracts. This package verifies both
providers satisfy the shared platform guarantees while preserving intentional
provider-specific differences. Slice 11.10 registered OpenRouter as an
explicit-only assess provider; Slice 11.11 added doctor local readiness
(no OpenRouter client construction or model invoke).

Registry decision (explicit): **B — Compatibility registry retained.**
``AssessAIProviderRegistry`` remains authoritative for ``codestrata assess``.
The contracts ``AIProviderRegistry`` stays available as an unwired platform
registry. Full consolidation is deferred because factory signatures differ
(``(settings) -> AIModelProvider`` vs ``() -> AIProvider``), entry-point
discovery and process-default wiring still belong to Assess, and removing
compatibility wrappers would change fail-soft exception translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "ai-provider-cross-provider-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "ai-provider-cross-provider-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.8"
SLICE_TITLE = "Cross-Provider Contract Verification"

ASSESSMENT_SCHEMA_VERSION = "1.2"

DEFAULT_PROVIDER = "bedrock"
EXPECTED_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
CANONICAL_PROVIDER_IDS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

BEDROCK_DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"
OPENAI_DEFAULT_ANSWER_MODEL = "gpt-4o-mini"

EXPECTED_MAXIMUM_ATTEMPTS = 1
EXPECTED_TIMEOUT_SECONDS = 60.0

# Explicit Slice 11.8 decision. Do not leave ambiguous.
REGISTRY_DECISION = "B"
REGISTRY_DECISION_LABEL = "compatibility_registry_retained"
REGISTRY_DECISION_RATIONALE = (
    "AssessAIProviderRegistry remains the assess-path authority because its "
    "factories take CodestrataSettings and return AIModelProvider wrappers; "
    "the contracts AIProviderRegistry uses zero-arg AIProvider factories and "
    "is not wired to assess, entry points, or doctor. Consolidation without "
    "behavior change requires a settings-aware bridge and is deferred."
)

FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = ("openrouter", "OpenRouter", "OPENROUTER")
ANALYTICS_ONLY_FAMILY_TOKENS: tuple[str, ...] = ("aws_bedrock",)

PRODUCT_PATH_SDK_FREE: tuple[str, ...] = (
    "application/assessment/service.py",
    "ai/enrichment/service.py",
    "ai/providers/factory.py",
    "extensions/assess_ai.py",
    "cli/assess.py",
)

CONTRACTS_PACKAGE = "ai/provider_contracts"
OPENAI_ADAPTER_PACKAGE = "ai/provider_adapters/openai"
BEDROCK_ADAPTER_PACKAGE = "ai/provider_adapters/bedrock"

WRAPPER_MODULES: tuple[str, ...] = (
    "ai/providers/openai_provider.py",
    "ai/providers/bedrock.py",
    "ai/providers/openrouter_provider.py",
)

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_provider_calls",
    "compatibility_wrappers_remain",
    "common_registry_consolidation_deferred",
    "wall_clock_timeout_client_owned",
    "operational_retry_remains_conservative",
    "doctor_uses_compatibility_path",
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

PRIOR_SLICE_IDS: tuple[str, ...] = ("11.1", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7")

OUTPUT_RELATIVE = "reports/verification/sv11-8"
REPORT_FILENAME = "ai-provider-cross-provider-verification.json"
REPORT_MD_FILENAME = "ai-provider-cross-provider-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 26

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")

SHARED_ERROR_CATEGORIES: tuple[str, ...] = (
    "authentication_failed",
    "authorization_failed",
    "dependency_unavailable",
    "internal_failure",
    "invalid_model",
    "invalid_request",
    "invalid_response",
    "missing_configuration",
    "parsing_failed",
    "provider_unavailable",
    "rate_limited",
    "timeout",
)

NON_RETRYABLE_BY_DEFAULT: tuple[str, ...] = (
    "authentication_failed",
    "authorization_failed",
    "invalid_model",
    "invalid_request",
    "invalid_response",
    "missing_configuration",
    "parsing_failed",
    "dependency_unavailable",
    "internal_failure",
)

POLICY_CONTROLLED_RETRYABLE: tuple[str, ...] = (
    "timeout",
    "rate_limited",
    "provider_unavailable",
)


@dataclass(frozen=True, slots=True)
class CrossProviderVerificationContract:
    """Pass/fail contract for SV.11.8 Cross-Provider Contract Verification."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    required_compatibility_requirement_ids: tuple[str, ...] = (
        REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    )
    registry_decision: str = REGISTRY_DECISION
    registry_decision_label: str = REGISTRY_DECISION_LABEL
    start_slice_11_9: bool = False
    add_openrouter: bool = False
    add_third_provider: bool = False
    change_defaults_or_selection: bool = False
    activate_max_retries: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.8 verifies OpenAI and Bedrock against shared Slice 11.2–11.5 "
            "contracts while recording intentional differences.",
            f"Registry decision {REGISTRY_DECISION}: {REGISTRY_DECISION_RATIONALE}",
            "PASS_WITH_LIMITATIONS is expected for an offline verification slice.",
        )
    )


def default_contract() -> CrossProviderVerificationContract:
    return CrossProviderVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "ANALYTICS_ONLY_FAMILY_TOKENS",
    "ASSESSMENT_SCHEMA_VERSION",
    "BEDROCK_ADAPTER_PACKAGE",
    "BEDROCK_DEFAULT_MODEL_ID",
    "CANONICAL_PROVIDER_IDS",
    "CONTRACTS_PACKAGE",
    "DEFAULT_PROVIDER",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "EXPECTED_REGISTERED_PROVIDERS",
    "EXPECTED_TIMEOUT_SECONDS",
    "FORBIDDEN_PROVIDER_TOKENS",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "NON_RETRYABLE_BY_DEFAULT",
    "OPENAI_ADAPTER_PACKAGE",
    "OPENAI_DEFAULT_ANSWER_MODEL",
    "OUTPUT_RELATIVE",
    "POLICY_CONTROLLED_RETRYABLE",
    "PRIOR_SLICE_IDS",
    "PRODUCT_PATH_SDK_FREE",
    "REGISTRY_DECISION",
    "REGISTRY_DECISION_LABEL",
    "REGISTRY_DECISION_RATIONALE",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SHARED_ERROR_CATEGORIES",
    "SLICE_ID",
    "SLICE_TITLE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "WRAPPER_MODULES",
    "CrossProviderVerificationContract",
    "default_contract",
]
