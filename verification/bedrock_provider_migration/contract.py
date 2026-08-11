"""Contract constants for SV.11.7 AWS Bedrock Provider Migration verification.

CodeStrata v0.2.0 Epic 11, Slice 11.7. Slice 11.6 migrated OpenAI onto the
Slice 11.2–11.5 provider contracts; Slice 11.7 completes the pair by
migrating Bedrock, the **default** provider. Both providers now run as
``AIProvider`` adapters under ``AIProviderExecutor`` while continuing to
present the legacy ``AIModelProvider`` interface to
``AiEnrichmentService`` through the same ``AssessAIProviderRegistry``.

This package verifies the migration's structure, its behavioral
compatibility with the Slice 11.1 baseline, the integrity of the AWS
credential boundary, its privacy properties, and its determinism — without
any real AWS call, credential read, instance metadata lookup, STS call, or
wall-clock wait.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_ID = "bedrock-provider-migration-verification"
VERIFICATION_VERSION = "1.0.0"

SCHEMA_NAME = "bedrock-provider-migration-verification"
SCHEMA_VERSION = "1.0.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.7"
SLICE_TITLE = "AWS Bedrock Provider Migration"

PACKAGE_DOTTED_NAME = "codestrata.ai.provider_adapters.bedrock"
PACKAGE_RELATIVE_PATH = "ai/provider_adapters/bedrock"
ADAPTERS_ROOT_RELATIVE_PATH = "ai/provider_adapters"
WRAPPER_RELATIVE_PATH = "ai/providers/bedrock.py"
AWS_CONFIG_RELATIVE_PATH = "ai/aws_config.py"

# The 12 modules Slice 11.7 adds under ai/provider_adapters/bedrock/.
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

# The single module in the adapter package permitted to reach AWS: to import
# boto3/botocore, or to call into ``codestrata.ai.aws_config``'s client
# factory. Everything else must stay SDK- and credential-free so import,
# capability discovery, and a disabled-AI run never touch either.
CREDENTIAL_BOUNDARY_MODULE = "client.py"

# ``legacy_bridge.py`` may import ``aws_config`` for one pure string
# formatter (``format_aws_authentication_error``), which reads no environment
# variable, imports no SDK, and contacts no AWS service.
AWS_CONFIG_IMPORTERS: tuple[str, ...] = ("client.py", "legacy_bridge.py")

# The only ``aws_config`` symbol the adapter is allowed to *call* outside the
# credential boundary module.
AWS_CONFIG_PURE_HELPERS: tuple[str, ...] = ("format_aws_authentication_error",)

# The AWS client factory the credential boundary must delegate to rather than
# reimplementing the credential chain.
AWS_CLIENT_FACTORY_NAME = "create_bedrock_runtime_client"

# Adapter package modules that may not appear in an ``import boto3`` line.
SDK_MODULE_NAMES: tuple[str, ...] = ("boto3", "botocore")

# Internal codestrata prefixes the adapter may depend on. Deliberately narrow:
# the contracts, the AWS boundary, the settings types, and the three legacy
# modules the wrapper must stay byte-compatible with.
ALLOWED_INTERNAL_IMPORT_PREFIXES: tuple[str, ...] = (
    "codestrata.ai.aws_config",
    "codestrata.ai.prompts.models",
    "codestrata.ai.provider_adapters",
    "codestrata.ai.provider_contracts",
    "codestrata.ai.providers.exceptions",
    "codestrata.ai.providers.models",
    "codestrata.ai.providers.parsing",
    "codestrata.config.settings",
)

# Layers the adapter must never reach. ``openai`` is listed because the
# Bedrock adapter must never borrow the OpenAI SDK or the OpenAI adapter.
FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "codestrata.ai.provider_adapters.openai",
    "codestrata.ai.providers.openai_provider",
    "codestrata.analytics",
    "codestrata.application",
    "codestrata.cli",
    "codestrata.datalake",
    "codestrata.extensions",
    "codestrata.platform",
    "codestrata.reporting",
    "codestrata.telemetry",
    "cursor",
    "openai",
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

# Files that must import the contracts now that Bedrock is migrated. The
# inverse of the prior slices' PRODUCT_PATH_FILES lists.
MIGRATED_PATH_FILES: tuple[str, ...] = (
    "ai/provider_adapters/bedrock/adapter.py",
    "ai/providers/bedrock.py",
)

# Files that must remain free of provider_contracts imports: the
# orchestration layers, the AWS boundary, and the CLI are explicitly *not*
# migrated by this slice.
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

# Orchestration files that must never import boto3/botocore: the AWS SDK
# belongs behind ``aws_config`` and the adapter's credential boundary.
# ``ai/providers/doctor.py`` is deliberately absent — it has always imported
# ``boto3`` inside a try/except to report whether the optional extra is
# installed, and this slice leaves that unchanged.
SDK_FREE_PATH_FILES: tuple[str, ...] = (
    "application/assessment/service.py",
    "ai/enrichment/service.py",
    "ai/providers/__init__.py",
    "ai/providers/bedrock.py",
    "ai/providers/factory.py",
    "extensions/assess_ai.py",
    "cli/assess.py",
)

# Surface anchors that must still be importable from the migrated wrapper:
# the Slice 11.1 baseline verification and the existing provider tests read
# these names off ``codestrata.ai.providers.bedrock``.
WRAPPER_REQUIRED_EXPORTS: tuple[str, ...] = (
    "BEDROCK_PROVIDER_NAME",
    "BedrockAIModelProvider",
    "build_converse_request",
    "extract_converse_response",
    "split_prompt_for_converse",
)

# Private helpers the Slice 11.1 baseline imports by name.
WRAPPER_REQUIRED_PRIVATE_HELPERS: tuple[str, ...] = (
    "_extract_usage",
    "_map_bedrock_exception",
)

WRAPPER_CONSTRUCTOR_PARAMETERS: tuple[str, ...] = (
    "self",
    "client",
    "region_name",
    "profile_name",
    "settings",
    "timeout_seconds",
)

# The wrapper must not gain a retry helper or an OpenRouter reference.
WRAPPER_FORBIDDEN_TOKENS: tuple[str, ...] = ("openrouter", "retry_call")

FORBIDDEN_PROVIDER_TOKENS: tuple[str, ...] = ("openrouter", "OpenRouter", "OPENROUTER")

# Behavior the migration must preserve exactly (Slice 11.1 baseline).
DEFAULT_PROVIDER = "bedrock"
BEDROCK_PROVIDER_NAME = "bedrock"
BEDROCK_DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"
# Every field on ``[ai.bedrock]``. The assess path reads model_id/region/
# timeout_seconds; embedding_model/answer_model/max_retries belong to other
# consumers and are listed here so an accidental key rename anywhere in the
# block is caught.
BEDROCK_CONFIG_KEYS: tuple[str, ...] = (
    "answer_model",
    "embedding_model",
    "max_retries",
    "model_id",
    "region",
    "timeout_seconds",
)
AWS_CONFIG_KEYS: tuple[str, ...] = ("profile", "region")
AWS_PROFILE_ENV_NAME = "AWS_PROFILE"
AWS_REGION_ENV_NAMES: tuple[str, ...] = ("AWS_REGION", "AWS_DEFAULT_REGION")

ASSESSMENT_SCHEMA_VERSION = "1.2"
INVOKE_CALLS_PER_ASSESS_RUN = 1
EXPECTED_MAXIMUM_ATTEMPTS = 1
# botocore's own retry handler stays pinned at one attempt so CodeStrata
# retries are never stacked on SDK retries (CR-1).
EXPECTED_SDK_MAX_ATTEMPTS = 1
EXPECTED_SDK_RETRY_MODE = "standard"
EXPECTED_TIMEOUT_SECONDS = 60.0
EXPECTED_REGISTERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")
DOCTOR_COVERED_PROVIDERS: tuple[str, ...] = ("bedrock", "openai", "openrouter")

STRUCTURED_JSON_INSTRUCTION = (
    "Respond with a single JSON object only. Do not include markdown fences or prose."
)
DEVELOPER_PREFIX = "Developer instructions:\n"
EXPECTED_MESSAGE_ROLES: tuple[str, ...] = ("user",)
EXPECTED_CONVERSE_KWARG_NAMES: tuple[str, ...] = (
    "inferenceConfig",
    "messages",
    "modelId",
    "system",
)
EXPECTED_INFERENCE_CONFIG_KEYS: tuple[str, ...] = ("maxTokens", "temperature")
# Bedrock Converse has no OpenAI-style ``response_format``: structured JSON is
# requested by prompt instruction only.
SUPPORTS_NATIVE_STRUCTURED_JSON = False
FORBIDDEN_REQUEST_KWARG_NAMES: tuple[str, ...] = (
    "max_tokens",
    "model",
    "response_format",
    "temperature",
)

# Converse response field names the adapter reads.
CONVERSE_USAGE_FIELDS: tuple[str, ...] = ("inputTokens", "outputTokens", "totalTokens")
CONVERSE_LATENCY_FIELD = "latencyMs"

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

# botocore exception class name -> expected error category. Matched by name
# because the adapter classifies by name and never imports the SDK to do so.
SDK_EXCEPTION_CATEGORY_MATRIX: dict[str, str] = {
    "ConnectTimeoutError": "timeout",
    "EndpointConnectionError": "timeout",
    "NoCredentialsError": "authentication_failed",
    "PartialCredentialsError": "authentication_failed",
    "ProfileNotFound": "authentication_failed",
    "ReadTimeoutError": "timeout",
    "SSOTokenLoadError": "authentication_failed",
    "TokenRetrievalError": "authentication_failed",
    "UnauthorizedSSOTokenError": "authentication_failed",
}

# AWS ``Error.Code`` on a ``ClientError`` -> expected error category.
SDK_ERROR_CODE_CATEGORY_MATRIX: dict[str, str] = {
    "AccessDeniedException": "authorization_failed",
    "AuthFailure": "authentication_failed",
    "ExpiredTokenException": "authentication_failed",
    "InternalServerException": "provider_unavailable",
    "InvalidRequestException": "invalid_request",
    "InvalidSignatureException": "authentication_failed",
    "ModelNotReadyException": "provider_unavailable",
    "ModelNotSupportedException": "invalid_model",
    "ModelTimeoutException": "timeout",
    "ResourceNotFoundException": "invalid_model",
    "ServiceQuotaExceededException": "rate_limited",
    "ServiceUnavailableException": "provider_unavailable",
    "ThrottlingException": "rate_limited",
    "TooManyRequestsException": "rate_limited",
    "UnauthorizedOperation": "authorization_failed",
    "UnrecognizedClientException": "authentication_failed",
    "ValidationException": "invalid_request",
}

# The legacy exception type each SDK failure must still raise through the
# compatibility wrapper, so enrichment fail-soft is unchanged.
LEGACY_EXCEPTION_MATRIX: dict[str, str] = {
    "AccessDeniedException": "AIProviderInvocationError",
    "ConnectTimeoutError": "AIProviderTimeoutError",
    "EndpointConnectionError": "AIProviderTimeoutError",
    "InternalServerException": "AIProviderTimeoutError",
    "ModelTimeoutException": "AIProviderTimeoutError",
    "NoCredentialsError": "AIProviderInvocationError",
    "ReadTimeoutError": "AIProviderTimeoutError",
    "ResourceNotFoundException": "AIProviderInvocationError",
    "ThrottlingException": "AIProviderTimeoutError",
    "UnrecognizedClientException": "AIProviderInvocationError",
    "ValidationException": "AIProviderInvocationError",
}

EXPECTED_LIMITATIONS: tuple[str, ...] = (
    "no_live_bedrock_calls",
    "compatibility_wrappers_remain",
    "operational_retry_remains_conservative",
    "doctor_uses_compatibility_path",
    "common_registry_consolidation_deferred",
    "wall_clock_timeout_sdk_owned",
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

PRIOR_SLICE_IDS: tuple[str, ...] = ("11.1", "11.2", "11.3", "11.4", "11.5", "11.6")

OUTPUT_RELATIVE = "reports/verification/sv11-7"
REPORT_FILENAME = "bedrock-provider-migration-verification.json"
REPORT_MD_FILENAME = "bedrock-provider-migration-verification.md"

NEGATIVE_SCENARIO_COUNT_MIN = 26

ALLOWED_VERDICTS: tuple[str, ...] = ("pass", "pass_with_limitations")


@dataclass(frozen=True, slots=True)
class BedrockMigrationVerificationContract:
    """Pass/fail contract for SV.11.7 AWS Bedrock Provider Migration."""

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
    default_model_id: str = BEDROCK_DEFAULT_MODEL_ID
    assessment_schema_version: str = ASSESSMENT_SCHEMA_VERSION
    start_slice_11_8: bool = False
    add_openrouter: bool = False
    change_default_provider: bool = False
    change_bedrock_config_keys: bool = False
    change_aws_credential_precedence: bool = False
    change_converse_semantics: bool = False
    change_prompt_content: bool = False
    change_cli_exit_behavior: bool = False
    activate_max_retries: bool = False
    stack_codestrata_retries_on_sdk_retries: bool = False
    change_migrated_openai_behavior: bool = False
    modify_telemetry_analytics_community_cloud_data_lake_vscode_cursor_infrastructure: bool = False
    use_real_network_or_credentials: bool = False
    commit_changes: bool = False
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "SV.11.7 verifies the migrated Bedrock adapter: its module inventory and "
            "dependency boundary, the integrity of the single AWS credential boundary, "
            "byte-compatible prompt/Converse request mapping, response and usage "
            "mapping, bounded error classification, executor wiring under a "
            "single-attempt retry policy, raise-based fail-soft translation, provider "
            "registry and selection, privacy, determinism, and the absence of any "
            "OpenAI regression.",
            "PASS_WITH_LIMITATIONS is expected: no_live_bedrock_calls, "
            "compatibility_wrappers_remain, operational_retry_remains_conservative, "
            "doctor_uses_compatibility_path, common_registry_consolidation_deferred, "
            "wall_clock_timeout_sdk_owned, openrouter_operational_explicit, and "
            "openrouter_doctor_local_readiness_only are recorded, intentional limitations.",
        )
    )


def default_contract() -> BedrockMigrationVerificationContract:
    return BedrockMigrationVerificationContract()


__all__ = [
    "ADAPTERS_ROOT_RELATIVE_PATH",
    "ALLOWED_INTERNAL_IMPORT_PREFIXES",
    "ALLOWED_VERDICTS",
    "ASSESSMENT_SCHEMA_VERSION",
    "AWS_CLIENT_FACTORY_NAME",
    "AWS_CONFIG_IMPORTERS",
    "AWS_CONFIG_KEYS",
    "AWS_CONFIG_PURE_HELPERS",
    "AWS_CONFIG_RELATIVE_PATH",
    "AWS_PROFILE_ENV_NAME",
    "AWS_REGION_ENV_NAMES",
    "BEDROCK_CONFIG_KEYS",
    "BEDROCK_DEFAULT_MODEL_ID",
    "BEDROCK_PROVIDER_NAME",
    "CONVERSE_LATENCY_FIELD",
    "CONVERSE_USAGE_FIELDS",
    "CREDENTIAL_BOUNDARY_MODULE",
    "DEFAULT_PROVIDER",
    "DEVELOPER_PREFIX",
    "EPIC",
    "EXPECTED_CONVERSE_KWARG_NAMES",
    "EXPECTED_INFERENCE_CONFIG_KEYS",
    "EXPECTED_LIMITATIONS",
    "EXPECTED_MAXIMUM_ATTEMPTS",
    "EXPECTED_MESSAGE_ROLES",
    "EXPECTED_MODULES",
    "EXPECTED_REGISTERED_PROVIDERS",
    "DOCTOR_COVERED_PROVIDERS",
    "EXPECTED_SDK_MAX_ATTEMPTS",
    "EXPECTED_SDK_RETRY_MODE",
    "EXPECTED_TIMEOUT_SECONDS",
    "FORBIDDEN_IMPORT_PREFIXES",
    "FORBIDDEN_PROVIDER_TOKENS",
    "FORBIDDEN_REQUEST_KWARG_NAMES",
    "FORBIDDEN_RUNTIME_IMPORT_MODULES",
    "INVOKE_CALLS_PER_ASSESS_RUN",
    "LEGACY_EXCEPTION_MATRIX",
    "LEGACY_PATH_FILES",
    "MIGRATED_PATH_FILES",
    "NEGATIVE_SCENARIO_COUNT_MIN",
    "NON_RETRYABLE_ERROR_CATEGORIES",
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
    "SDK_ERROR_CODE_CATEGORY_MATRIX",
    "SDK_EXCEPTION_CATEGORY_MATRIX",
    "SDK_FREE_PATH_FILES",
    "SDK_MODULE_NAMES",
    "SLICE_ID",
    "SLICE_TITLE",
    "STRUCTURED_JSON_INSTRUCTION",
    "SUPPORTS_NATIVE_STRUCTURED_JSON",
    "VERIFICATION_ID",
    "VERIFICATION_VERSION",
    "WRAPPER_CONSTRUCTOR_PARAMETERS",
    "WRAPPER_FORBIDDEN_TOKENS",
    "WRAPPER_RELATIVE_PATH",
    "WRAPPER_REQUIRED_EXPORTS",
    "WRAPPER_REQUIRED_PRIVATE_HELPERS",
    "BedrockMigrationVerificationContract",
    "default_contract",
]
