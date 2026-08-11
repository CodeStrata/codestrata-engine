"""Map OpenAI SDK failures onto bounded ``ErrorCategory``/``AIProviderError`` values.

Two separate things are produced from one SDK exception:

1. An :class:`AIProviderError` carrying only a bounded category, a stable
   machine-safe code, and a **fixed** safe-prose detail. It never contains
   raw exception text, an exception class name, a stack trace, a base URL, a
   model value, a request ID, or a filesystem path.
2. A ``legacy_detail`` string — the sanitized exception text
   (``sanitize_provider_text``) that the pre-migration provider embedded in
   its raised ``AIProviderError`` subclasses. It exists purely so
   ``legacy_bridge`` can rebuild byte-identical legacy exception messages for
   the enrichment fail-soft path; it is never placed on the
   ``AIProviderError`` data object, never returned through an
   ``AIProviderResult``, and never recorded in a verification report.

Retryability is *not* decided here. It is a property of the configured
``AIProviderRetryPolicy`` (Slice 11.4), whose default partition already
classifies ``timeout``/``rate_limited``/``provider_unavailable`` as retryable
and everything else as non-retryable. :data:`RETRYABLE_CATEGORIES` restates
that partition for documentation/verification only.
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
CODE_MISSING_DEPENDENCY = "openai_optional_extra_missing"
CODE_MISSING_API_KEY = "openai_api_key_env_not_set"
CODE_CLIENT_CONSTRUCTION_FAILED = "openai_client_construction_failed"
CODE_AUTHENTICATION_FAILED = "openai_authentication_failed"
CODE_AUTHORIZATION_FAILED = "openai_authorization_failed"
CODE_INVALID_MODEL = "openai_invalid_model"
CODE_INVALID_REQUEST = "openai_invalid_request"
CODE_TIMEOUT = "openai_request_timeout"
CODE_RATE_LIMITED = "openai_rate_limited"
CODE_PROVIDER_UNAVAILABLE = "openai_provider_unavailable"
CODE_EMPTY_RESPONSE = "openai_response_missing_assistant_text"
CODE_UNREADABLE_RESPONSE = "openai_response_unreadable"
CODE_PARSING_FAILED = "openai_response_parsing_failed"
CODE_PROMPT_MAPPING_FAILED = "openai_prompt_mapping_failed"
CODE_UNEXPECTED_INVOCATION_FAILURE = "openai_unexpected_invocation_failure"

# Fixed, safe-prose details. Bounded (<= 240 chars) and free of any value
# that came from configuration, credentials, prompts, or an SDK response.
_DETAILS: dict[str, str] = {
    CODE_MISSING_DEPENDENCY: "The optional openai extra is not installed.",
    CODE_MISSING_API_KEY: "No API key was found in the configured environment variable.",
    CODE_CLIENT_CONSTRUCTION_FAILED: "The OpenAI client could not be constructed.",
    CODE_AUTHENTICATION_FAILED: "The provider rejected the supplied credentials.",
    CODE_AUTHORIZATION_FAILED: "The credentials are not permitted to use this model.",
    CODE_INVALID_MODEL: "The requested model is unknown to the provider.",
    CODE_INVALID_REQUEST: "The provider rejected the request as invalid.",
    CODE_TIMEOUT: "The provider request timed out.",
    CODE_RATE_LIMITED: "The provider rate-limited the request.",
    CODE_PROVIDER_UNAVAILABLE: "The provider was temporarily unavailable.",
    CODE_EMPTY_RESPONSE: "The provider response contained no assistant text.",
    CODE_UNREADABLE_RESPONSE: "The provider response could not be read.",
    CODE_PARSING_FAILED: "The provider response could not be parsed as the expected contract.",
    CODE_PROMPT_MAPPING_FAILED: "The request could not be mapped to a provider call.",
    CODE_UNEXPECTED_INVOCATION_FAILURE: "The provider invocation failed unexpectedly.",
}

CATEGORY_BY_CODE: dict[str, ErrorCategory] = {
    CODE_MISSING_DEPENDENCY: ErrorCategory.DEPENDENCY_UNAVAILABLE,
    CODE_MISSING_API_KEY: ErrorCategory.MISSING_CONFIGURATION,
    CODE_CLIENT_CONSTRUCTION_FAILED: ErrorCategory.MISSING_CONFIGURATION,
    CODE_AUTHENTICATION_FAILED: ErrorCategory.AUTHENTICATION_FAILED,
    CODE_AUTHORIZATION_FAILED: ErrorCategory.AUTHORIZATION_FAILED,
    CODE_INVALID_MODEL: ErrorCategory.INVALID_MODEL,
    CODE_INVALID_REQUEST: ErrorCategory.INVALID_REQUEST,
    CODE_TIMEOUT: ErrorCategory.TIMEOUT,
    CODE_RATE_LIMITED: ErrorCategory.RATE_LIMITED,
    CODE_PROVIDER_UNAVAILABLE: ErrorCategory.PROVIDER_UNAVAILABLE,
    CODE_EMPTY_RESPONSE: ErrorCategory.INVALID_RESPONSE,
    CODE_UNREADABLE_RESPONSE: ErrorCategory.INVALID_RESPONSE,
    CODE_PARSING_FAILED: ErrorCategory.PARSING_FAILED,
    CODE_PROMPT_MAPPING_FAILED: ErrorCategory.INVALID_REQUEST,
    CODE_UNEXPECTED_INVOCATION_FAILURE: ErrorCategory.INTERNAL_FAILURE,
}

# OpenAI SDK exception class names -> diagnostic code. Matched by *name*, not
# by importing the SDK: this module must stay importable (and testable) with
# no openai package installed, and must never trigger an SDK import as a side
# effect of classifying a failure.
SDK_EXCEPTION_NAME_TO_CODE: dict[str, str] = {
    "AuthenticationError": CODE_AUTHENTICATION_FAILED,
    "PermissionDeniedError": CODE_AUTHORIZATION_FAILED,
    "NotFoundError": CODE_INVALID_MODEL,
    "BadRequestError": CODE_INVALID_REQUEST,
    "UnprocessableEntityError": CODE_INVALID_REQUEST,
    "APITimeoutError": CODE_TIMEOUT,
    "RateLimitError": CODE_RATE_LIMITED,
    "APIConnectionError": CODE_PROVIDER_UNAVAILABLE,
    "InternalServerError": CODE_PROVIDER_UNAVAILABLE,
}

RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    ErrorCategory(value) for value in DEFAULT_RETRYABLE_ERROR_CATEGORIES
)
NON_RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    ErrorCategory(value) for value in DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES
)


@dataclass(frozen=True, slots=True)
class MappedFailure:
    """A bounded provider error plus the bridge-only sanitized legacy detail."""

    error: AIProviderError
    legacy_detail: str = ""


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


def classify_sdk_exception(error: BaseException) -> MappedFailure:
    """Classify an exception raised by the OpenAI SDK by its class name only."""

    code = SDK_EXCEPTION_NAME_TO_CODE.get(type(error).__name__, CODE_UNEXPECTED_INVOCATION_FAILURE)
    return MappedFailure(error=build_error(code), legacy_detail=sanitize_provider_text(str(error)))


def classify_client_construction_failure(error: BaseException) -> MappedFailure:
    """Classify a failure raised while constructing the OpenAI client itself."""

    return MappedFailure(
        error=build_error(CODE_CLIENT_CONSTRUCTION_FAILED),
        legacy_detail=sanitize_provider_text(str(error)),
    )


def classify_unreadable_response(error: BaseException) -> MappedFailure:
    """Classify a failure raised while reading fields off an SDK response object."""

    return MappedFailure(
        error=build_error(CODE_UNREADABLE_RESPONSE),
        legacy_detail=sanitize_provider_text(str(error)),
    )


def is_retryable(category: ErrorCategory) -> bool:
    """Return whether ``category`` is retryable under the default Slice 11.4 partition."""

    return category in RETRYABLE_CATEGORIES


__all__ = [
    "CATEGORY_BY_CODE",
    "CODE_AUTHENTICATION_FAILED",
    "CODE_AUTHORIZATION_FAILED",
    "CODE_CLIENT_CONSTRUCTION_FAILED",
    "CODE_EMPTY_RESPONSE",
    "CODE_INVALID_MODEL",
    "CODE_INVALID_REQUEST",
    "CODE_MISSING_API_KEY",
    "CODE_MISSING_DEPENDENCY",
    "CODE_PARSING_FAILED",
    "CODE_PROMPT_MAPPING_FAILED",
    "CODE_PROVIDER_UNAVAILABLE",
    "CODE_RATE_LIMITED",
    "CODE_TIMEOUT",
    "CODE_UNEXPECTED_INVOCATION_FAILURE",
    "CODE_UNREADABLE_RESPONSE",
    "NON_RETRYABLE_CATEGORIES",
    "RETRYABLE_CATEGORIES",
    "SDK_EXCEPTION_NAME_TO_CODE",
    "MappedFailure",
    "build_error",
    "classify_client_construction_failure",
    "classify_sdk_exception",
    "classify_unreadable_response",
    "is_retryable",
]
