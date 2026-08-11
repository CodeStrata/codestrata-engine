"""Map AWS SDK failures onto bounded ``ErrorCategory``/``AIProviderError`` values.

Two separate things are produced from one SDK exception:

1. An :class:`AIProviderError` carrying only a bounded category, a stable
   machine-safe code, and a **fixed** safe-prose detail. It never contains
   raw exception text, an exception class name, an AWS error code, a stack
   trace, an account ID, an ARN, an endpoint, a region, a profile name, a
   model value, a request ID, or a filesystem path.
2. A ``legacy_detail`` string — the sanitized exception text
   (``sanitize_provider_text``) that the pre-migration provider embedded in
   its raised ``AIProviderError`` subclasses, plus an optional
   ``legacy_label`` (the AWS error code or exception class name) that the
   legacy "Bedrock service error (<label>)" message interpolated. Both exist
   purely so ``legacy_bridge`` can rebuild byte-identical legacy exception
   messages for the enrichment fail-soft path; neither is ever placed on the
   ``AIProviderError`` data object, returned through an ``AIProviderResult``,
   or recorded in a verification report.

Classification is by **exception class name and AWS error code only**. This
module never imports ``boto3``/``botocore``: it must stay importable (and
testable) with no AWS SDK installed, and must never trigger an SDK import as
a side effect of classifying a failure.

The name/code partitions and their evaluation order reproduce the
pre-migration ``bedrock._map_bedrock_exception`` ladder exactly. Reordering
them is a behavior change.

Retryability is *not* decided here. It is a property of the configured
``AIProviderRetryPolicy`` (Slice 11.4). :data:`RETRYABLE_CATEGORIES` restates
that default partition for documentation/verification only.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import AIProviderError, ErrorCategory
from codestrata.ai.provider_contracts.execution_policy import (
    DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES,
    DEFAULT_RETRYABLE_ERROR_CATEGORIES,
)
from codestrata.ai.providers.parsing import sanitize_provider_text

# Stable, machine-safe diagnostic codes. These are part of this adapter's
# observable surface: `legacy_bridge` keys the legacy exception type and
# message off the code, so renaming one is a behavior change.
CODE_MISSING_DEPENDENCY = "bedrock_optional_extra_missing"
CODE_CLIENT_AUTHENTICATION_FAILED = "bedrock_client_authentication_failed"
CODE_CLIENT_CONSTRUCTION_FAILED = "bedrock_client_construction_failed"
CODE_AUTHENTICATION_FAILED = "bedrock_authentication_failed"
CODE_AWS_AUTHENTICATION_ERROR = "bedrock_aws_authentication_error"
CODE_AUTHORIZATION_FAILED = "bedrock_model_access_denied"
CODE_INVALID_MODEL = "bedrock_invalid_model"
CODE_INVALID_REQUEST = "bedrock_invalid_request"
CODE_TIMEOUT = "bedrock_request_timeout"
CODE_MODEL_TIMEOUT = "bedrock_model_timeout"
CODE_RATE_LIMITED = "bedrock_rate_limited"
CODE_PROVIDER_UNAVAILABLE = "bedrock_provider_unavailable"
CODE_SERVICE_ERROR = "bedrock_service_error"
CODE_RESPONSE_NOT_A_MAPPING = "bedrock_response_not_a_mapping"
CODE_RESPONSE_MISSING_OUTPUT = "bedrock_response_missing_output"
CODE_RESPONSE_MISSING_MESSAGE = "bedrock_response_missing_output_message"
CODE_RESPONSE_MISSING_CONTENT = "bedrock_response_missing_output_message_content"
CODE_EMPTY_RESPONSE = "bedrock_response_missing_assistant_text"
CODE_UNREADABLE_RESPONSE = "bedrock_response_unreadable"
CODE_PARSING_FAILED = "bedrock_response_parsing_failed"
CODE_PROMPT_MAPPING_FAILED = "bedrock_prompt_mapping_failed"
CODE_UNEXPECTED_INVOCATION_FAILURE = "bedrock_unexpected_invocation_failure"

# Fixed, safe-prose details. Bounded (<= 240 chars) and free of any value
# that came from configuration, credentials, prompts, or an SDK response.
_DETAILS: dict[str, str] = {
    CODE_MISSING_DEPENDENCY: "The optional bedrock extra is not installed.",
    CODE_CLIENT_AUTHENTICATION_FAILED: "AWS authentication failed while building the client.",
    CODE_CLIENT_CONSTRUCTION_FAILED: "The Bedrock Runtime client could not be constructed.",
    CODE_AUTHENTICATION_FAILED: "The provider rejected the supplied credentials.",
    CODE_AWS_AUTHENTICATION_ERROR: "AWS authentication failed for the Bedrock invocation.",
    CODE_AUTHORIZATION_FAILED: "The credentials are not permitted to use this model.",
    CODE_INVALID_MODEL: "The requested model is unknown to the provider.",
    CODE_INVALID_REQUEST: "The provider rejected the request as invalid.",
    CODE_TIMEOUT: "The provider request timed out.",
    CODE_MODEL_TIMEOUT: "The model did not respond within the service limit.",
    CODE_RATE_LIMITED: "The provider rate-limited the request.",
    CODE_PROVIDER_UNAVAILABLE: "The provider was temporarily unavailable.",
    CODE_SERVICE_ERROR: "The provider returned a service error.",
    CODE_RESPONSE_NOT_A_MAPPING: "The provider response was not a mapping.",
    CODE_RESPONSE_MISSING_OUTPUT: "The provider response was missing its output block.",
    CODE_RESPONSE_MISSING_MESSAGE: "The provider response was missing its output message.",
    CODE_RESPONSE_MISSING_CONTENT: "The provider response was missing its message content.",
    CODE_EMPTY_RESPONSE: "The provider response contained no assistant text.",
    CODE_UNREADABLE_RESPONSE: "The provider response could not be read.",
    CODE_PARSING_FAILED: "The provider response could not be parsed as the expected contract.",
    CODE_PROMPT_MAPPING_FAILED: "The request could not be mapped to a provider call.",
    CODE_UNEXPECTED_INVOCATION_FAILURE: "The provider invocation failed unexpectedly.",
}

CATEGORY_BY_CODE: dict[str, ErrorCategory] = {
    CODE_MISSING_DEPENDENCY: ErrorCategory.DEPENDENCY_UNAVAILABLE,
    CODE_CLIENT_AUTHENTICATION_FAILED: ErrorCategory.MISSING_CONFIGURATION,
    CODE_CLIENT_CONSTRUCTION_FAILED: ErrorCategory.MISSING_CONFIGURATION,
    CODE_AUTHENTICATION_FAILED: ErrorCategory.AUTHENTICATION_FAILED,
    CODE_AWS_AUTHENTICATION_ERROR: ErrorCategory.AUTHENTICATION_FAILED,
    CODE_AUTHORIZATION_FAILED: ErrorCategory.AUTHORIZATION_FAILED,
    CODE_INVALID_MODEL: ErrorCategory.INVALID_MODEL,
    CODE_INVALID_REQUEST: ErrorCategory.INVALID_REQUEST,
    CODE_TIMEOUT: ErrorCategory.TIMEOUT,
    CODE_MODEL_TIMEOUT: ErrorCategory.TIMEOUT,
    CODE_RATE_LIMITED: ErrorCategory.RATE_LIMITED,
    CODE_PROVIDER_UNAVAILABLE: ErrorCategory.PROVIDER_UNAVAILABLE,
    CODE_SERVICE_ERROR: ErrorCategory.INTERNAL_FAILURE,
    CODE_RESPONSE_NOT_A_MAPPING: ErrorCategory.INVALID_RESPONSE,
    CODE_RESPONSE_MISSING_OUTPUT: ErrorCategory.INVALID_RESPONSE,
    CODE_RESPONSE_MISSING_MESSAGE: ErrorCategory.INVALID_RESPONSE,
    CODE_RESPONSE_MISSING_CONTENT: ErrorCategory.INVALID_RESPONSE,
    CODE_EMPTY_RESPONSE: ErrorCategory.INVALID_RESPONSE,
    CODE_UNREADABLE_RESPONSE: ErrorCategory.INVALID_RESPONSE,
    CODE_PARSING_FAILED: ErrorCategory.PARSING_FAILED,
    CODE_PROMPT_MAPPING_FAILED: ErrorCategory.INVALID_REQUEST,
    CODE_UNEXPECTED_INVOCATION_FAILURE: ErrorCategory.INTERNAL_FAILURE,
}

# botocore/boto3 exception class names -> diagnostic code, matched by name.
CREDENTIAL_EXCEPTION_NAMES: frozenset[str] = frozenset(
    {
        "NoCredentialsError",
        "PartialCredentialsError",
        "ProfileNotFound",
        "UnauthorizedSSOTokenError",
        "TokenRetrievalError",
        "SSOTokenLoadError",
    }
)

TIMEOUT_EXCEPTION_NAMES: frozenset[str] = frozenset(
    {"ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError"}
)

GENERIC_SERVICE_EXCEPTION_NAMES: frozenset[str] = frozenset({"BotoCoreError", "ClientError"})

SDK_EXCEPTION_NAME_TO_CODE: dict[str, str] = {
    **{name: CODE_AUTHENTICATION_FAILED for name in sorted(CREDENTIAL_EXCEPTION_NAMES)},
    **{name: CODE_TIMEOUT for name in sorted(TIMEOUT_EXCEPTION_NAMES)},
}

# AWS ``Error.Code`` values -> diagnostic code.
SDK_ERROR_CODE_TO_CODE: dict[str, str] = {
    "AuthFailure": CODE_AUTHENTICATION_FAILED,
    "ExpiredTokenException": CODE_AUTHENTICATION_FAILED,
    "InvalidSignatureException": CODE_AUTHENTICATION_FAILED,
    "UnrecognizedClientException": CODE_AUTHENTICATION_FAILED,
    "AccessDeniedException": CODE_AUTHORIZATION_FAILED,
    "UnauthorizedOperation": CODE_AUTHORIZATION_FAILED,
    "ServiceQuotaExceededException": CODE_RATE_LIMITED,
    "ThrottlingException": CODE_RATE_LIMITED,
    "TooManyRequestsException": CODE_RATE_LIMITED,
    "InternalServerException": CODE_PROVIDER_UNAVAILABLE,
    "ModelNotReadyException": CODE_PROVIDER_UNAVAILABLE,
    "ServiceUnavailableException": CODE_PROVIDER_UNAVAILABLE,
    "ModelTimeoutException": CODE_MODEL_TIMEOUT,
    "InvalidRequestException": CODE_INVALID_REQUEST,
    "ValidationException": CODE_INVALID_REQUEST,
    "ModelNotSupportedException": CODE_INVALID_MODEL,
    "ResourceNotFoundException": CODE_INVALID_MODEL,
}

RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    ErrorCategory(value) for value in DEFAULT_RETRYABLE_ERROR_CATEGORIES
)
NON_RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    ErrorCategory(value) for value in DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES
)

AWS_AUTHENTICATION_ERROR_NAME = "AwsAuthenticationError"


@dataclass(frozen=True, slots=True)
class MappedFailure:
    """A bounded provider error plus the bridge-only sanitized legacy detail."""

    error: AIProviderError
    legacy_detail: str = ""
    legacy_label: str = ""


def build_error(code: str) -> AIProviderError:
    """Build a bounded ``AIProviderError`` for a known diagnostic ``code``."""

    category = CATEGORY_BY_CODE.get(code)
    if category is None:
        category = ErrorCategory.INTERNAL_FAILURE
        code = CODE_UNEXPECTED_INVOCATION_FAILURE
    return AIProviderError(
        category=category,
        code=code,
        detail=_DETAILS.get(code, _DETAILS[CODE_UNEXPECTED_INVOCATION_FAILURE]),
    )


def client_error_code(error: BaseException) -> str | None:
    """Read ``response["Error"]["Code"]`` off a botocore ``ClientError``, if present."""

    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    error_payload = response.get("Error")
    if not isinstance(error_payload, dict):
        return None
    code = error_payload.get("Code")
    return str(code) if code is not None else None


def classify_sdk_exception(error: BaseException) -> MappedFailure:
    """Classify an exception raised by the AWS SDK during a Converse call.

    Follows the pre-migration ladder: credential class names, then timeout
    class names, then AWS error codes (auth, access denied, temporary,
    validation), then a generic service error, then an unexpected failure.
    """

    exception_name = type(error).__name__
    if exception_name == AWS_AUTHENTICATION_ERROR_NAME:
        # aws_config already formatted actionable, secret-free guidance; the
        # pre-migration provider re-raised it verbatim.
        return MappedFailure(
            error=build_error(CODE_AWS_AUTHENTICATION_ERROR), legacy_detail=str(error)
        )

    message = sanitize_provider_text(str(error))
    code = client_error_code(error)

    diagnostic_code = SDK_EXCEPTION_NAME_TO_CODE.get(exception_name)
    if diagnostic_code is None and code is not None:
        diagnostic_code = SDK_ERROR_CODE_TO_CODE.get(code)
    if diagnostic_code is not None:
        return MappedFailure(error=build_error(diagnostic_code), legacy_detail=message)

    if exception_name in GENERIC_SERVICE_EXCEPTION_NAMES or code:
        return MappedFailure(
            error=build_error(CODE_SERVICE_ERROR),
            legacy_detail=message,
            legacy_label=code or exception_name,
        )

    return MappedFailure(
        error=build_error(CODE_UNEXPECTED_INVOCATION_FAILURE), legacy_detail=message
    )


def classify_client_authentication_failure(error: BaseException) -> MappedFailure:
    """Classify an ``AwsAuthenticationError`` raised while constructing the client."""

    return MappedFailure(
        error=build_error(CODE_CLIENT_AUTHENTICATION_FAILED), legacy_detail=str(error)
    )


def classify_client_construction_failure(error: BaseException) -> MappedFailure:
    """Classify a failure raised while constructing the Bedrock Runtime client."""

    return MappedFailure(
        error=build_error(CODE_CLIENT_CONSTRUCTION_FAILED),
        legacy_detail=sanitize_provider_text(str(error)),
    )


def classify_missing_dependency(error: BaseException) -> MappedFailure:
    """Classify the "boto3 is not installed" failure raised by ``aws_config``."""

    return MappedFailure(
        error=build_error(CODE_MISSING_DEPENDENCY),
        legacy_detail=sanitize_provider_text(str(error)),
    )


def classify_unreadable_response(error: BaseException) -> MappedFailure:
    """Classify a failure raised while reading fields off a Converse response."""

    return MappedFailure(
        error=build_error(CODE_UNREADABLE_RESPONSE),
        legacy_detail=sanitize_provider_text(str(error)),
    )


def is_retryable(category: ErrorCategory) -> bool:
    """Return whether ``category`` is retryable under the default Slice 11.4 partition."""

    return category in RETRYABLE_CATEGORIES


__all__ = [
    "AWS_AUTHENTICATION_ERROR_NAME",
    "CATEGORY_BY_CODE",
    "CODE_AUTHENTICATION_FAILED",
    "CODE_AUTHORIZATION_FAILED",
    "CODE_AWS_AUTHENTICATION_ERROR",
    "CODE_CLIENT_AUTHENTICATION_FAILED",
    "CODE_CLIENT_CONSTRUCTION_FAILED",
    "CODE_EMPTY_RESPONSE",
    "CODE_INVALID_MODEL",
    "CODE_INVALID_REQUEST",
    "CODE_MISSING_DEPENDENCY",
    "CODE_MODEL_TIMEOUT",
    "CODE_PARSING_FAILED",
    "CODE_PROMPT_MAPPING_FAILED",
    "CODE_PROVIDER_UNAVAILABLE",
    "CODE_RATE_LIMITED",
    "CODE_RESPONSE_MISSING_CONTENT",
    "CODE_RESPONSE_MISSING_MESSAGE",
    "CODE_RESPONSE_MISSING_OUTPUT",
    "CODE_RESPONSE_NOT_A_MAPPING",
    "CODE_SERVICE_ERROR",
    "CODE_TIMEOUT",
    "CODE_UNEXPECTED_INVOCATION_FAILURE",
    "CODE_UNREADABLE_RESPONSE",
    "CREDENTIAL_EXCEPTION_NAMES",
    "GENERIC_SERVICE_EXCEPTION_NAMES",
    "NON_RETRYABLE_CATEGORIES",
    "RETRYABLE_CATEGORIES",
    "SDK_ERROR_CODE_TO_CODE",
    "SDK_EXCEPTION_NAME_TO_CODE",
    "TIMEOUT_EXCEPTION_NAMES",
    "MappedFailure",
    "build_error",
    "classify_client_authentication_failure",
    "classify_client_construction_failure",
    "classify_missing_dependency",
    "classify_sdk_exception",
    "classify_unreadable_response",
    "client_error_code",
    "is_retryable",
]
