"""Contract constants for SV.11.10 OpenRouter Configuration & Authentication verification.

CodeStrata v0.2.0 Epic 11, Slice 11.10 wires OpenRouter into
``AssessAIProviderRegistry`` (explicit-only; Bedrock remains default) with
``[ai.openrouter]`` settings, env-backed credentials, and model resolution.
Slice 11.11 added doctor local readiness for OpenRouter (no client construction
or model invoke). Decision B keeps ``AssessAIProviderRegistry`` authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "openrouter-configuration-verification"
VERIFICATION_VERSION = "1.0.0"
SCHEMA_NAME = "openrouter-configuration-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.10"
SLICE_TITLE = "OpenRouter Configuration and Authentication"

PROVIDER_ID = "openrouter"
DEFAULT_PROVIDER = "bedrock"
ASSESS_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

CODESTRATA_OPENROUTER_MODEL_ID_ENV = "CODESTRATA_OPENROUTER_MODEL_ID"
DEFAULT_API_KEY_ENV = "OPENROUTER_API_KEY"

# Test-only synthetic model — never a product default.
TEST_ONLY_MODEL = "test-only/openrouter-model"

EXPECTED_OPENROUTER_SETTINGS_FIELDS: tuple[str, ...] = (
    "model",
    "api_key_env",
    "base_url",
    "site_url",
    "app_name",
    "timeout_seconds",
    "max_retries",
)

FORBIDDEN_OPENROUTER_SETTINGS_FIELDS: tuple[str, ...] = (
    "api_key",
    "headers",
    "authorization",
    "http_referer",
    "x_title",
)

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_openrouter_calls",
    "model_catalog_not_validated",
    "compatibility_registry_retained",
    "operational_retry_conservative",
    "wall_clock_timeout_client_owned",
    "openrouter_doctor_local_readiness_only",
)

OUTPUT_RELATIVE = "reports/verification/sv11-10"
REPORT_FILENAME = "openrouter-configuration-verification.json"
REPORT_MD_FILENAME = "openrouter-configuration-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 26
ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
BEDROCK_DEFAULT_MODEL = "amazon.nova-lite-v1:0"
EXPECTED_MAXIMUM_ATTEMPTS = 1


@dataclass(frozen=True, slots=True)
class OpenRouterConfigurationVerificationContract:
    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    start_slice_11_11: bool = False
    modify_doctor: bool = False
    change_default_provider: bool = False
    change_openai_or_bedrock_defaults: bool = False
    live_openrouter_calls: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.10 proves OpenRouter configuration and authentication wiring "
            "for explicit assess selection without changing Bedrock defaults.",
            "PASS_WITH_LIMITATIONS expected: no live OpenRouter calls; model catalog "
            "not validated; Decision B registry retained; doctor local readiness "
            "only (Slice 11.11; no client construction or model invoke).",
            "Optional identification headers (site_url / app_name) are implemented.",
        )
    )


def default_contract() -> OpenRouterConfigurationVerificationContract:
    return OpenRouterConfigurationVerificationContract()


__all__ = [
    "ALLOWED_VERDICTS",
    "ASSESS_REGISTERED_PROVIDERS",
    "BEDROCK_DEFAULT_MODEL",
    "CODESTRATA_OPENROUTER_MODEL_ID_ENV",
    "DEFAULT_API_KEY_ENV",
    "DEFAULT_PROVIDER",
    "EPIC",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "EXPECTED_OPENROUTER_SETTINGS_FIELDS",
    "FORBIDDEN_OPENROUTER_SETTINGS_FIELDS",
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
    "OpenRouterConfigurationVerificationContract",
    "default_contract",
]
