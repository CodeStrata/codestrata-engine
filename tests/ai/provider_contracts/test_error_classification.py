"""Tests for ``classify_error``/``classify_unexpected_exception``. No exception text leaks."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.error_classification import (
    UNEXPECTED_EXCEPTION_SAFE_CODE,
    ProviderErrorClassification,
    classify_error,
    classify_unexpected_exception,
)
from codestrata.ai.provider_contracts.errors import (
    AIProviderError,
    ErrorCategory,
    ProviderContractValidationError,
)
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_RETRY_POLICY,
    AIProviderRetryPolicy,
)


def test_classify_error_reflects_the_error_category_and_code() -> None:
    error = AIProviderError(category=ErrorCategory.TIMEOUT, code="fake_timeout")
    retry_policy = AIProviderRetryPolicy(retryable_categories=frozenset({ErrorCategory.TIMEOUT}))
    classification = classify_error(error, retry_policy)
    assert classification.category is ErrorCategory.TIMEOUT
    assert classification.safe_code == "fake_timeout"
    assert classification.retryable is True


def test_classify_error_reports_non_retryable_when_policy_excludes_the_category() -> None:
    error = AIProviderError(category=ErrorCategory.INVALID_REQUEST, code="fake_invalid")
    classification = classify_error(error, DEFAULT_RETRY_POLICY)
    assert classification.retryable is False


def test_classify_error_rejects_non_ai_provider_error() -> None:
    with pytest.raises(ProviderContractValidationError):
        classify_error("not-an-error", DEFAULT_RETRY_POLICY)  # type: ignore[arg-type]


def test_classify_error_rejects_invalid_retry_policy() -> None:
    error = AIProviderError(category=ErrorCategory.TIMEOUT, code="x")
    with pytest.raises(ProviderContractValidationError):
        classify_error(error, "not-a-policy")  # type: ignore[arg-type]


def test_classify_unexpected_exception_always_uses_internal_failure_and_fixed_safe_code() -> None:
    classification = classify_unexpected_exception(DEFAULT_RETRY_POLICY)
    assert classification.category is ErrorCategory.INTERNAL_FAILURE
    assert classification.safe_code == UNEXPECTED_EXCEPTION_SAFE_CODE


def test_classify_unexpected_exception_never_takes_an_exception_argument() -> None:
    import inspect

    signature = inspect.signature(classify_unexpected_exception)
    assert list(signature.parameters) == ["retry_policy"]


def test_classify_unexpected_exception_rejects_invalid_retry_policy() -> None:
    with pytest.raises(ProviderContractValidationError):
        classify_unexpected_exception("not-a-policy")  # type: ignore[arg-type]


def test_provider_error_classification_rejects_invalid_category() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderErrorClassification(category="timeout", retryable=True, safe_code="x")  # type: ignore[arg-type]


def test_provider_error_classification_rejects_non_bool_retryable() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderErrorClassification(
            category=ErrorCategory.TIMEOUT, retryable="yes", safe_code="x"  # type: ignore[arg-type]
        )


def test_provider_error_classification_rejects_empty_safe_code() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderErrorClassification(category=ErrorCategory.TIMEOUT, retryable=True, safe_code="")
