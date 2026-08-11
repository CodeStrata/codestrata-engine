"""``ProviderErrorClassification``: bounded, safe classification of a failure outcome.

Never carries raw exception text or SDK exception class names — only the
already-bounded ``ErrorCategory``, whether the configured retry policy
considers that category retryable, and a short, fixed "safe code" (either
the originating ``AIProviderError.code`` or, for an unexpected exception
caught by ``executor.py``, the fixed ``UNEXPECTED_EXCEPTION_SAFE_CODE``
literal, which never echoes the exception's message or type name).
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import (
    AIProviderError,
    ErrorCategory,
    ProviderContractValidationError,
)
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy

UNEXPECTED_EXCEPTION_SAFE_CODE = "internal_failure_unexpected_exception"


@dataclass(frozen=True, slots=True)
class ProviderErrorClassification:
    """A bounded, safe-to-log classification of why an attempt did not succeed."""

    category: ErrorCategory
    retryable: bool
    safe_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.category, ErrorCategory):
            raise ProviderContractValidationError(
                f"category must be an ErrorCategory, got {type(self.category).__name__}"
            )
        if not isinstance(self.retryable, bool):
            raise ProviderContractValidationError("retryable must be a bool")
        if not isinstance(self.safe_code, str) or not self.safe_code.strip():
            raise ProviderContractValidationError("safe_code must be a non-empty string")


def classify_error(
    error: AIProviderError, retry_policy: AIProviderRetryPolicy
) -> ProviderErrorClassification:
    """Classify an already-bounded ``AIProviderError`` against ``retry_policy``."""

    if not isinstance(error, AIProviderError):
        raise ProviderContractValidationError("error must be an AIProviderError")
    if not isinstance(retry_policy, AIProviderRetryPolicy):
        raise ProviderContractValidationError("retry_policy must be an AIProviderRetryPolicy")
    return ProviderErrorClassification(
        category=error.category,
        retryable=retry_policy.is_retryable(error.category),
        safe_code=error.code,
    )


def classify_unexpected_exception(
    retry_policy: AIProviderRetryPolicy,
) -> ProviderErrorClassification:
    """Classify an unexpected (non-fail-soft) exception. Never inspects the exception itself.

    Always ``ErrorCategory.INTERNAL_FAILURE`` with the fixed
    ``UNEXPECTED_EXCEPTION_SAFE_CODE`` — callers (``executor.py``) must never
    pass this function the exception's message, type name, or traceback.
    """

    if not isinstance(retry_policy, AIProviderRetryPolicy):
        raise ProviderContractValidationError("retry_policy must be an AIProviderRetryPolicy")
    return ProviderErrorClassification(
        category=ErrorCategory.INTERNAL_FAILURE,
        retryable=retry_policy.is_retryable(ErrorCategory.INTERNAL_FAILURE),
        safe_code=UNEXPECTED_EXCEPTION_SAFE_CODE,
    )


__all__ = [
    "UNEXPECTED_EXCEPTION_SAFE_CODE",
    "ProviderErrorClassification",
    "classify_error",
    "classify_unexpected_exception",
]
