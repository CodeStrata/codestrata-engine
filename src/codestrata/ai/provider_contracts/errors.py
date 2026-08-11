"""Bounded error categories and safe diagnostic error objects.

``AIProviderError`` is a *data* object carried inside an ``AIProviderResult``
(see ``responses.py``) — it is never a raised exception, and it never carries
raw exception text, stack traces, credentials, or filesystem paths. Only a
bounded category, a short machine-safe code, and a short safe-prose detail
are permitted.

``ProviderContractValidationError`` is the exception this package raises when
a contract value object (request/result/usage/...) is constructed with
invalid data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.provider_contracts.policy import ALLOWED_ERROR_CATEGORIES

_MAX_DETAIL_LENGTH = 240
_MAX_CODE_LENGTH = 80

# Substrings that must never appear in a bounded diagnostic detail. This is a
# defense-in-depth check, not a substitute for callers doing the right thing:
# adapters must construct AIProviderError from safe, pre-sanitized strings.
_UNSAFE_DETAIL_SUBSTRINGS: tuple[str, ...] = (
    "Traceback (most recent call last)",
    "-----BEGIN",
    "/Users/",
    "/home/",
    "Authorization: Bearer",
)


class ProviderContractValidationError(ValueError):
    """Raised when a provider-contract value object violates its invariants."""


class ErrorCategory(StrEnum):
    """Bounded, adapter-neutral failure categories.

    This is deliberately a small, closed set. Adapters must map SDK-specific
    exceptions (botocore ``ClientError`` codes, openai SDK exception classes,
    ...) onto one of these categories rather than exposing SDK error types
    through the contract.
    """

    MISSING_CONFIGURATION = "missing_configuration"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    INVALID_MODEL = "invalid_model"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_REQUEST = "invalid_request"
    INVALID_RESPONSE = "invalid_response"
    PARSING_FAILED = "parsing_failed"
    INTERNAL_FAILURE = "internal_failure"


assert tuple(category.value for category in ErrorCategory) == ALLOWED_ERROR_CATEGORIES, (
    "ErrorCategory enum values must exactly match policy.ALLOWED_ERROR_CATEGORIES"
)


@dataclass(frozen=True, slots=True)
class AIProviderError:
    """A bounded, safe-to-log description of why a provider call did not succeed."""

    category: ErrorCategory
    code: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.category, ErrorCategory):
            raise ProviderContractValidationError(
                f"category must be an ErrorCategory, got {type(self.category).__name__}"
            )
        code = self.code.strip()
        if not code:
            raise ProviderContractValidationError("code must be a non-empty diagnostic code")
        if len(code) > _MAX_CODE_LENGTH:
            raise ProviderContractValidationError(
                f"code must be at most {_MAX_CODE_LENGTH} characters"
            )
        if len(self.detail) > _MAX_DETAIL_LENGTH:
            raise ProviderContractValidationError(
                f"detail must be at most {_MAX_DETAIL_LENGTH} characters "
                "(raw exception text/stack traces are never permitted here)"
            )
        for forbidden in _UNSAFE_DETAIL_SUBSTRINGS:
            if forbidden in self.detail:
                raise ProviderContractValidationError(
                    f"detail must not contain unsafe content: {forbidden!r}"
                )


__all__ = [
    "AIProviderError",
    "ErrorCategory",
    "ProviderContractValidationError",
]
