"""Contract constants for SV.11.6 OpenAI Provider Migration verification.

CodeStrata v0.2.0 Epic 11, Slice 11.6. Slice 11.6 migrated **only** OpenAI
onto the Slice 11.2–11.5 provider contracts, leaving the engine in *mixed
mode*: the same ``AssessAIProviderRegistry`` served a contract-based OpenAI
adapter and a legacy Bedrock provider. This package verifies the migration's
structure, its behavioral compatibility with the Slice 11.1 baseline, its
privacy properties, and its determinism, without any real provider network
access, credential, or wall-clock wait.

**Slice 11.7 migrated Bedrock.** The mixed-mode state this suite was written
against is therefore historical: both providers now run on the contracts, and
the Bedrock-side checks below assert Bedrock's *migrated* shape rather than
its pre-migration one. What SV.11.6 continues to own is unchanged — the
OpenAI adapter's structure, boundary, mappings, and privacy. Bedrock's own
migration is verified by ``verification.bedrock_provider_migration``
(SV.11.7).

The ``bedrock_remains_legacy`` limitation label is retained deliberately.
``codestrata.ai.provider_adapters.openai.adapter.ADAPTER_LIMITATIONS`` still
emits it on every OpenAI result, and freezing that tuple is what keeps
Slice 11.7 from changing migrated OpenAI behavior. Read it as "the label
Slice 11.6 froze", not as a current statement about Bedrock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "openai-provider-migration-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "openai-provider-migration-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.6"
SLICE_TITLE = "OpenAI Provider Migration"

PACKAGE_DOTTED_NAME = "codestrata.ai.provider_adapters.openai"
PACKAGE_RELATIVE_PATH = "ai/provider_adapters/openai"
ADAPTERS_ROOT_RELATIVE_PATH = "ai/provider_adapters"

# The 12 modules Slice 11.6 adds under ai/provider_adapters/openai/.
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

# The single module in the adapter package permitted to import the ``openai``
# SDK or read ``os.environ``. Everything else must stay SDK- and
# credential-free so import, capability discovery, and a disabled-AI run never
# touch either.
CREDENTIAL_BOUNDARY_MODULE = "client.py"

# Internal codestrata prefixes the adapter may depend on. Deliberately narrow:
# the contracts, the settings types, and the three legacy modules the wrapper
# must stay byte-compatible with.
ALLOWED_INTERNAL_IMPORT_PREFIXES: tuple[str, ...] = (
    "codestrata.ai.prompts.models",
    "codestrata.ai.provider_adapters",
    "codestrata.ai.provider_contracts",
    "codestrata.ai.providers.exceptions",
    "codestrata.ai.providers.models",
    "codestrata.ai.providers.parsing",
    "codestrata.config.settings",
)

# Layers the adapter must never reach.
FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "boto3",
    "botocore",
    "codestrata.analytics",
    "codestrata.application",
    "codestrata.cli",
    "codestrata.datalake",
    "codestrata.extensions",
    "codestrata.platform",
    "codestrata.reporting",
    "codestrata.telemetry",
    "cursor",
    "vscode",
)

# Modules that must never appear anywhere in the adapter package: no waiting,
# no shelling out, no direct network client.
FORBIDDEN_RUNTIME_IMPORT_MODULES: tuple[str, ...] = (
    "asyncio",
    "httpx",
    "requests",
    "signal",
    "socket",
    "subprocess",
    "threading",
    "urllib",
)

# Files that must import the contracts now that OpenAI is migrated. The
# inverse of the prior slices' PRODUCT_PATH_FILES lists.
MIGRATED_PATH_FILES: tuple[str, ...] = (
    "ai/provider_adapters/openai/adapter.py",
    "ai/providers/openai_provider.py",
)

# Files that must remain free of provider_contracts imports: the
# orchestration layers are explicitly *not* migrated by this slice, and
# Slice 11.7 did not migrate them either. ``ai/providers/bedrock.py`` was on
# this list until Slice 11.7 turned it into a compatibility wrapper over
# ``ai/provider_adapters/bedrock/``; SV.11.7 asserts the positive direction
# for it now.
LEGACY_PATH_FILES: tuple[str, ...] = (
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

# Orchestration files that must never import the OpenAI SDK: the SDK belongs
# behind the adapter's credential boundary. ``ai/providers/doctor.py`` is
# deliberately absent — it has always imported ``openai`` inside a try/except to
# report whether the optional extra is installed, and this slice leaves that
# unchanged.
SDK_FREE_PATH_FILES: tuple[str, ...] = (
    "application/assessment/service.py",
    "ai/enrichment/service.py",
    "ai/providers/__init__.py",
    "ai/providers/factory.py",
    "ai/providers/openai_provider.py",
    "extensions/assess_ai.py",
    "cli/assess.py",
)

# Bedrock's own migration is Slice 11.7's subject; what SV.11.6 still asserts
# about it is that this slice's OpenAI work did not leak into it and that
# OpenRouter completed in Slices 11.9–11.11; see ai_provider_platform_completion.
BEDROCK_MODULE_RELATIVE_PATH = "ai/providers/bedrock.py"
BEDROCK_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "openrouter",
    "provider_adapters.openai",
    "retry_call",
)
# Surface anchors that must still be present in bedrock.py. Slice 11.7 turned
# the module into a compatibility wrapper, so these pin the public surface the
# Slice 11.1 baseline and the existing provider tests import — not the wire
# call, which now lives in ``ai/provider_adapters/bedrock/adapter.py``.
BEDROCK_REQUIRED_TOKENS: tuple[str, ...] = (
    "BedrockAIModelProvider",
    "build_converse_request",
    "def invoke(",
    "extract_converse_response",
    "split_prompt_for_converse",
)

FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = ("openrouter", "OpenRouter", "OPENROUTER")

# Behavior the migration must preserve exactly (Slice 11.1 baseline).
DEFAULT_PROVIDER = "bedrock"
OPENAI_PROVIDER_NAME = "openai"
OPENAI_DEFAULT_ANSWER_MODEL = "gpt-4o-mini"
OPENAI_API_KEY_ENV_DEFAULT = "OPENAI_API_KEY"
# Every field on ``[ai.openai]``. The assess path reads answer_model/api_key_env/
# base_url; embedding_* and timeout_seconds belong to other consumers and are
# listed here so an accidental key rename anywhere in the block is caught.
OPENAI_CONFIG_KEYS: tuple[str, ...] = (
    "answer_model",
    "api_key_env",
    "base_url",
    "embedding_dimensions",
    "embedding_model",
    "max_retries",
    "timeout_seconds",
)
ASSESSMENT_SCHEMA_VERSION = "1.2"
INVOKE_CALLS_PER_ASSESS_RUN = 1
EXPECTED_MAXIMUM_ATTEMPTS = 1
EXPECTED_TIMEOUT_SECONDS = 60.0
EXPECTED_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
DOCTOR_COVERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

STRUCTURED_JSON_INSTRUCTION = (
    "Respond with a single JSON object only. Do not include markdown fences or prose."
)
DEVELOPER_PREFIX = "Developer instructions:\n"
JSON_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}
EXPECTED_MESSAGE_ROLES: tuple[str, ...] = ("system", "user")
EXPECTED_CHAT_KWARG_NAMES: tuple[str, ...] = (
    "max_tokens",
    "messages",
    "model",
    "response_format",
    "temperature",
)

# The bounded error categories the adapter must be able to produce.
REQUIRED_ERROR_CATEGORIES: tuple[str, ...] = (
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

RETRYABLE_ERROR_CATEGORIES: tuple[str, ...] = (
    "provider_unavailable",
    "rate_limited",
    "timeout",
)

NON_RETRYABLE_ERROR_CATEGORIES: tuple[str, ...] = (
    "authentication_failed",
    "authorization_failed",
    "dependency_unavailable",
    "internal_failure",
    "invalid_model",
    "invalid_request",
    "invalid_response",
    "missing_configuration",
    "parsing_failed",
)

# OpenAI SDK exception class name -> expected error category. Matched by name
# because the adapter classifies by name and never imports the SDK to do so.
SDK_EXCEPTION_CATEGORY_MATRIX: dict[str, str] = {
    "APIConnectionError": "provider_unavailable",
    "APITimeoutError": "timeout",
    "AuthenticationError": "authentication_failed",
    "BadRequestError": "invalid_request",
    "InternalServerError": "provider_unavailable",
    "NotFoundError": "invalid_model",
    "PermissionDeniedError": "authorization_failed",
    "RateLimitError": "rate_limited",
    "UnprocessableEntityError": "invalid_request",
}

# The legacy exception type each SDK failure must still raise through the
# compatibility wrapper, so enrichment fail-soft is unchanged.
LEGACY_EXCEPTION_MATRIX: dict[str, str] = {
    "APIConnectionError": "AIProviderTimeoutError",
    "APITimeoutError": "AIProviderTimeoutError",
    "AuthenticationError": "AIProviderInvocationError",
    "BadRequestError": "AIProviderInvocationError",
    "InternalServerError": "AIProviderTimeoutError",
    "NotFoundError": "AIProviderInvocationError",
    "PermissionDeniedError": "AIProviderInvocationError",
    "RateLimitError": "AIProviderTimeoutError",
    "UnprocessableEntityError": "AIProviderInvocationError",
}

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "bedrock_remains_legacy",
    "mixed_mode_provider_architecture",
    "no_live_openai_calls",
    "operational_retry_remains_conservative",
    "doctor_uses_compatibility_path",
    "executor_limitation_labels_predate_migration",
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

PRIOR_SLICE_IDS: tuple[str, ...] = ("11.1", "11.2", "11.3", "11.4", "11.5")

OUTPUT_RELATIVE = "reports/verification/sv11-6"
REPORT_FILENAME = "openai-provider-migration-verification.json"
REPORT_MD_FILENAME = "openai-provider-migration-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 26

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")


@dataclass(frozen=True, slots=True)
class OpenAIMigrationVerificationContract:
    """Pass/fail contract for SV.11.6 OpenAI Provider Migration."""

    verification_id: str = VERIFICATION_ID
    verification_version: str = VERIFICATION_VERSION
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    epic: str = EPIC
    slice_id: str = SLICE_ID
    allowed_verdicts: tuple[str, ...] = ALLOWED_VERDICTS
    expected_limitations: tuple[str, ...] = EXPECTED_LIMITATIONS
    required_compatibility_requirement_ids: tuple[str, ...] = REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    default_provider: str = DEFAULT_PROVIDER
    assessment_schema_version: str = ASSESSMENT_SCHEMA_VERSION
    start_slice_11_7: bool = False
    migrate_bedrock: bool = False
    add_openrouter: bool = False
    change_default_provider: bool = False
    change_openai_config_keys: bool = False
    change_prompt_content: bool = False
    change_cli_exit_behavior: bool = False
    activate_max_retries: bool = False
    modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure: bool = False
    use_real_network_or_credentials: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.6 verifies the migrated OpenAI adapter: its module inventory and "
            "dependency boundary, byte-compatible prompt/request mapping, response and "
            "usage mapping, bounded error classification, executor wiring under a "
            "single-attempt retry policy, raise-based fail-soft translation, mixed-mode "
            "coexistence with legacy Bedrock, privacy, and determinism.",
            "PASS_WITH_LIMITATIONS is expected: bedrock_remains_legacy, "
            "mixed_mode_provider_architecture, no_live_openai_calls, "
            "operational_retry_remains_conservative, doctor_uses_compatibility_path, "
            "executor_limitation_labels_predate_migration, openrouter_operational_explicit, "
            "and openrouter_doctor_local_readiness_only are recorded, intentional limitations.",
        )
    )


def default_contract() -> OpenAIMigrationVerificationContract:
    return OpenAIMigrationVerificationContract()


__all__ = [
    "ADAPTERS_ROOT_RELATIVE_PATH",
    "ALLOWED_INTERNAL_IMPORT_PREFIXES",
    "ALLOWED_VERDICTS",
    "ASSESSMENT_SCHEMA_VERSION",
    "BEDROCK_FORBIDDEN_TOKENS",
    "BEDROCK_MODULE_RELATIVE_PATH",
    "BEDROCK_REQUIRED_TOKENS",
    "CREDENTIAL_BOUNDARY_MODULE",
    "DEFAULT_PROVIDER",
    "DEVELOPER_PREFIX",
    "EPIC",
    "EXPECTED_CHAT_KWARG_NAMES",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "EXPECTED_MESSAGE_ROLES",
    "EXPECTED_MODULES",
    "EXPECTED_REGISTERED_PROVIDERS",
    "DOCTOR_COVERED_PROVIDERS",
    "EXPECTED_TIMEOUT_SECONDS",
    "FORBIDDEN_IMPORT_PREFIXES",
    "FORBIDDEN_PROVIDER_TOKENS",
    "FORBIDDEN_RUNTIME_IMPORT_MODULES",
    "INVOKE_CALLS_PER_ASSESS_RUN",
    "JSON_RESPONSE_FORMAT",
    "LEGACY_EXCEPTION_MATRIX",
    "LEGACY_PATH_FILES",
    "MIGRATED_PATH_FILES",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "NON_RETRYABLE_ERROR_CATEGORIES",
    "OPENAI_API_KEY_ENV_DEFAULT",
    "OPENAI_CONFIG_KEYS",
    "OPENAI_DEFAULT_ANSWER_MODEL",
    "OPENAI_PROVIDER_NAME",
    "OUTPUT_RELATIVE",
    "PACKAGE_DOTTED_NAME",
    "PACKAGE_RELATIVE_PATH",
    "PRIOR_SLICE_IDS",
    "REPORT_FILENAME",
    "REPORT_MD_FILENAME",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "REQUIRED_ERROR_CATEGORIES",
    "RETRYABLE_ERROR_CATEGORIES",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "SDK_EXCEPTION_CATEGORY_MATRIX",
    "SDK_FREE_PATH_FILES",
    "SLICE_ID",
    "SLICE_TITLE",
    "STRUCTURED_JSON_INSTRUCTION",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "OpenAIMigrationVerificationContract",
    "default_contract",
]
