"""Contract constants for SV.11.12 AI Provider Privacy Boundary Verification.

CodeStrata v0.2.0 Epic 11, Slice 11.12 verifies privacy, failure-isolation,
and architecture boundaries across bedrock, openai, and openrouter. Mocked
clients only. Decision B retains ``AssessAIProviderRegistry``. Bedrock remains
the default provider. No live provider calls. No real credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "ai-provider-privacy-boundary-verification"
VERIFICATION_VERSION = "1.0.0"
SCHEMA_NAME = "ai-provider-privacy-boundary-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.12"
SLICE_TITLE = "Provider Privacy, Failure-Isolation, and Boundary Verification"

PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
DEFAULT_PROVIDER = "bedrock"
ASSESS_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

REGISTRY_DECISION = "B"
REGISTRY_DECISION_LABEL = "compatibility_registry_retained"

ASSESSMENT_SCHEMA_VERSION = "1.2"
EXPECTED_MAXIMUM_ATTEMPTS = 1

NEGATIVE_SCENARIO_COUNT_MIN = 26

REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

OUTPUT_RELATIVE = "reports/verification/sv11-12"
REPORT_FILENAME = "ai-provider-privacy-boundary-verification.json"
REPORT_MD_FILENAME = "ai-provider-privacy-boundary-verification.md"

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_provider_calls",
    "no_real_credentials",
    "no_remote_model_validation",
    "no_remote_credential_validation",
    "compatibility_registry_retained",
    "operational_retry_conservative",
    "wall_clock_timeout_client_owned",
    "no_full_external_extension_host_or_cloud_validation",
)

# Presence-only diagnostic keys (union of adapter / result / execution views).
ALLOWED_ADAPTER_DIAGNOSTIC_KEYS: frozenset[str] = frozenset(
    {
        "adapter_limitations",
        "api_key_env_name",
        "api_key_present",
        "app_name_configured",
        "base_url_configured",
        "client_injected",
        "max_retries_declared",
        "profile_configured",
        "provider_id",
        "region_configured",
        "site_url_configured",
        "supported_capability_ids",
        "supports_structured_json",
        "timeout_seconds",
    }
)

ALLOWED_RESULT_DIAGNOSTIC_KEYS: frozenset[str] = frozenset(
    {
        "capability",
        "contract_version",
        "error_category",
        "error_code",
        "has_content",
        "has_usage",
        "limitations",
        "provider_id",
        "status",
    }
)

ALLOWED_EXECUTION_DIAGNOSTIC_KEYS: frozenset[str] = frozenset(
    {
        "attempts",
        "capability",
        "diagnostics",
        "has_usage",
        "limitations",
        "provider_id",
        "provider_result",
        "retry_count",
        "status",
        "terminal_error_category",
        "timeout_applied",
    }
)

ALLOWED_DIAGNOSTIC_KEYS: frozenset[str] = (
    ALLOWED_ADAPTER_DIAGNOSTIC_KEYS
    | ALLOWED_RESULT_DIAGNOSTIC_KEYS
    | ALLOWED_EXECUTION_DIAGNOSTIC_KEYS
)

DOCTOR_FORBIDDEN_CALL_TOKENS: tuple[str, ...] = (
    "invoke(",
    "execute(",
    "chat.completions",
    "OpenAI(",
    "resolve_client(",
)

CLI_FORBIDDEN_FLAG_TOKENS: tuple[str, ...] = (
    "--openrouter-api-key",
    "--api-key",
    "--aws-access-key",
    "--send-test",
)

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "codestrata.platform",
    "codestrata.datalake",
    "codestrata_platform",
    "codestrata_datalake",
    "codestrata.telemetry",
    "codestrata.analytics",
)

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
BEDROCK_DEFAULT_MODEL = "amazon.nova-lite-v1:0"

AI_EXECUTION_STATUS_VALUES: tuple[str, ...] = (
    "authentication_failed",
    "not_requested",
    "parsing_failed",
    "provider_failed",
    "succeeded",
    "validation_failed",
)


@dataclass(frozen=True, slots=True)
class AIProviderPrivacyBoundaryVerificationContract:
    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    registry_decision: str = REGISTRY_DECISION
    start_slice_11_13: bool = False
    live_provider_calls: bool = False
    change_default_provider: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.12 proves privacy, failure-isolation, and architecture "
            "boundaries across bedrock, openai, and openrouter.",
            "PASS_WITH_LIMITATIONS expected: no live provider calls; no real "
            "credentials; Decision B registry retained; operational retry "
            "remains conservative.",
        )
    )


def default_contract() -> AIProviderPrivacyBoundaryVerificationContract:
    return AIProviderPrivacyBoundaryVerificationContract()


__all__ = [
    "ALLOWED_ADAPTER_DIAGNOSTIC_KEYS",
    "ALLOWED_DIAGNOSTIC_KEYS",
    "ALLOWED_EXECUTION_DIAGNOSTIC_KEYS",
    "ALLOWED_RESULT_DIAGNOSTIC_KEYS",
    "ALLOWED_VERDICTS",
    "AI_EXECUTION_STATUS_VALUES",
    "ASSESSMENT_SCHEMA_VERSION",
    "ASSESS_REGISTERED_PROVIDERS",
    "BEDROCK_DEFAULT_MODEL",
    "CLI_FORBIDDEN_FLAG_TOKENS",
    "DEFAULT_PROVIDER",
    "DOCTOR_FORBIDDEN_CALL_TOKENS",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "FORBIDDEN_IMPORT_PREFIXES",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OPENAI_DEFAULT_MODEL",
    "OUTPUT_RELATIVE",
    "PROVIDERS",
    "REGISTRY_DECISION",
    "REGISTRY_DECISION_LABEL",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SLICE_ID",
    "SLICE_TITLE",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "AIProviderPrivacyBoundaryVerificationContract",
    "default_contract",
]
