"""Unit tests for provider_contracts.errors."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import (
    AIProviderError,
    ErrorCategory,
    ProviderContractValidationError,
)


def test_error_categories_are_bounded_set() -> None:
    assert {c.value for c in ErrorCategory} == {
        "missing_configuration",
        "dependency_unavailable",
        "authentication_failed",
        "authorization_failed",
        "invalid_model",
        "timeout",
        "rate_limited",
        "provider_unavailable",
        "invalid_request",
        "invalid_response",
        "parsing_failed",
        "internal_failure",
    }


def test_valid_error_construction() -> None:
    error = AIProviderError(
        category=ErrorCategory.AUTHENTICATION_FAILED,
        code="missing_api_key",
        detail="required API key was not configured",
    )
    assert error.category is ErrorCategory.AUTHENTICATION_FAILED
    assert error.code == "missing_api_key"


def test_error_detail_defaults_to_empty_string() -> None:
    error = AIProviderError(category=ErrorCategory.INTERNAL_FAILURE, code="unknown")
    assert error.detail == ""


def test_error_rejects_empty_code() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderError(category=ErrorCategory.INTERNAL_FAILURE, code="   ")


def test_error_rejects_overlong_detail() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderError(category=ErrorCategory.INTERNAL_FAILURE, code="x", detail="a" * 241)


@pytest.mark.parametrize(
    "unsafe_detail",
    [
        "Traceback (most recent call last):\n  File x",
        "-----BEGIN PRIVATE KEY-----",
        "/Users/someone/secret.py",
        "/home/someone/secret.py",
        "Authorization: Bearer abcdef",
    ],
)
def test_error_rejects_unsafe_detail_content(unsafe_detail: str) -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderError(category=ErrorCategory.INTERNAL_FAILURE, code="x", detail=unsafe_detail)


def test_error_rejects_non_category_type() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderError(category="timeout", code="x")  # type: ignore[arg-type]


def test_error_never_carries_raw_exception_instance() -> None:
    # AIProviderError has no field that could hold an Exception object.
    error = AIProviderError(category=ErrorCategory.TIMEOUT, code="t", detail="d")
    for value in (error.category, error.code, error.detail):
        assert not isinstance(value, BaseException)
