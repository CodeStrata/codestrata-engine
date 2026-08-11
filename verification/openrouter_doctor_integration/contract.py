"""Contract constants for SV.11.11 OpenRouter Doctor & Integration verification.

CodeStrata v0.2.0 Epic 11, Slice 11.11 adds privacy-safe OpenRouter readiness
to ``codestrata ai doctor`` and mocked end-to-end integration for the explicit
OpenRouter assess path. No live OpenRouter calls. Decision B retains
``AssessAIProviderRegistry``. Bedrock remains the default provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "openrouter-doctor-integration-verification"
VERIFICATION_VERSION = "1.0.0"
SCHEMA_NAME = "openrouter-doctor-integration-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.11"
SLICE_TITLE = "OpenRouter Doctor and Integration Verification"

PROVIDER_ID = "openrouter"
DEFAULT_PROVIDER = "bedrock"
ASSESS_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

CODESTRATA_OPENROUTER_MODEL_ID_ENV = "CODESTRATA_OPENROUTER_MODEL_ID"
DEFAULT_API_KEY_ENV = "OPENROUTER_API_KEY"

# Test-only synthetic model — never a product default.
TEST_ONLY_MODEL = "test-only/openrouter-model"

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_openrouter_calls",
    "credential_not_remotely_validated",
    "model_not_remotely_validated",
    "compatibility_registry_retained",
    "operational_retry_conservative",
    "wall_clock_timeout_client_owned",
    "no_full_external_extension_host_or_cloud_validation",
)

OUTPUT_RELATIVE = "reports/verification/sv11-11"
REPORT_FILENAME = "openrouter-doctor-integration-verification.json"
REPORT_MD_FILENAME = "openrouter-doctor-integration-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 26
ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
BEDROCK_DEFAULT_MODEL = "amazon.nova-lite-v1:0"
EXPECTED_MAXIMUM_ATTEMPTS = 1
ASSESSMENT_SCHEMA_VERSION = "1.2"

DOCTOR_FORBIDDEN_CALL_TOKENS: tuple[str, ...] = (
    "invoke(",
    "execute(",
    "chat.completions",
    "OpenAI(",
    "resolve_client(",
)

DOCTOR_FORBIDDEN_ADAPTER_IMPORT = "provider_adapters.openrouter"


@dataclass(frozen=True, slots=True)
class OpenRouterDoctorIntegrationVerificationContract:
    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    start_slice_11_12: bool = False
    live_openrouter_calls: bool = False
    change_default_provider: bool = False
    change_openai_or_bedrock_defaults: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.11 proves OpenRouter doctor local readiness and mocked "
            "end-to-end integration without live provider calls.",
            "PASS_WITH_LIMITATIONS expected: no live OpenRouter calls; "
            "credentials and models are not remotely validated; Decision B "
            "registry retained; operational retry remains conservative.",
        )
    )


def default_contract() -> OpenRouterDoctorIntegrationVerificationContract:
    return OpenRouterDoctorIntegrationVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "ASSESSMENT_SCHEMA_VERSION",
    "ASSESS_REGISTERED_PROVIDERS",
    "BEDROCK_DEFAULT_MODEL",
    "CODESTRATA_OPENROUTER_MODEL_ID_ENV",
    "DEFAULT_API_KEY_ENV",
    "DEFAULT_PROVIDER",
    "DOCTOR_FORBIDDEN_ADAPTER_IMPORT",
    "DOCTOR_FORBIDDEN_CALL_TOKENS",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "OPENAI_DEFAULT_MODEL",
    "OUTPUT_RELATIVE",
    "PROVIDER_ID",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SLICE_ID",
    "SLICE_TITLE",
    "TEST_ONLY_MODEL",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "OpenRouterDoctorIntegrationVerificationContract",
    "default_contract",
]
