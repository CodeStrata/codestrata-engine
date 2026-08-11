"""Tests for ``AIProviderRetryPolicy`` and ``max_retries_to_maximum_attempts``."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_NON_RETRYABLE_CATEGORIES,
    DEFAULT_RETRY_POLICY,
    DEFAULT_RETRYABLE_CATEGORIES,
    SETTINGS_REPRESENTABLE_RETRY_POLICY,
    AIProviderRetryPolicy,
    max_retries_to_maximum_attempts,
)


def test_default_retry_policy_makes_exactly_one_attempt() -> None:
    assert DEFAULT_RETRY_POLICY.maximum_attempts == 1


def test_settings_representable_retry_policy_maps_three_retries_to_four_attempts() -> None:
    assert SETTINGS_REPRESENTABLE_RETRY_POLICY.maximum_attempts == 4


def test_settings_representable_retry_policy_is_not_the_default() -> None:
    assert SETTINGS_REPRESENTABLE_RETRY_POLICY != DEFAULT_RETRY_POLICY


@pytest.mark.parametrize(
    ("max_retries", "expected"), [(0, 1), (1, 2), (3, 4), (9, 10)]
)
def test_max_retries_to_maximum_attempts_adds_one(max_retries: int, expected: int) -> None:
    assert max_retries_to_maximum_attempts(max_retries) == expected


def test_max_retries_to_maximum_attempts_rejects_negative() -> None:
    with pytest.raises(ProviderContractValidationError):
        max_retries_to_maximum_attempts(-1)


def test_max_retries_to_maximum_attempts_rejects_non_int() -> None:
    with pytest.raises(ProviderContractValidationError):
        max_retries_to_maximum_attempts(3.5)  # type: ignore[arg-type]
    with pytest.raises(ProviderContractValidationError):
        max_retries_to_maximum_attempts(True)  # type: ignore[arg-type]


def test_default_categories_are_disjoint_and_cover_all_categories() -> None:
    assert DEFAULT_RETRYABLE_CATEGORIES.isdisjoint(DEFAULT_NON_RETRYABLE_CATEGORIES)
    assert DEFAULT_RETRYABLE_CATEGORIES | DEFAULT_NON_RETRYABLE_CATEGORIES == set(ErrorCategory)


def test_is_retryable_reflects_the_configured_set() -> None:
    policy = AIProviderRetryPolicy(retryable_categories=frozenset({ErrorCategory.TIMEOUT}))
    assert policy.is_retryable(ErrorCategory.TIMEOUT) is True
    assert policy.is_retryable(ErrorCategory.INVALID_REQUEST) is False


def test_retry_policy_accepts_a_source_category() -> None:
    policy = AIProviderRetryPolicy(source_category=SourceCategory.DEFAULT)
    assert policy.source_category is SourceCategory.DEFAULT


def test_retry_policy_rejects_zero_maximum_attempts() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(maximum_attempts=0)


def test_retry_policy_rejects_negative_maximum_attempts() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(maximum_attempts=-1)


def test_retry_policy_rejects_maximum_attempts_above_ceiling() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(maximum_attempts=11)


def test_retry_policy_rejects_bool_maximum_attempts() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(maximum_attempts=True)  # type: ignore[arg-type]


def test_retry_policy_rejects_non_frozenset_retryable_categories() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(retryable_categories={ErrorCategory.TIMEOUT})  # type: ignore[arg-type]


def test_retry_policy_rejects_non_error_category_members() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(retryable_categories=frozenset({"timeout"}))  # type: ignore[arg-type]


def test_retry_policy_rejects_invalid_source_category() -> None:
    with pytest.raises(ProviderContractValidationError):
        AIProviderRetryPolicy(source_category="cli")  # type: ignore[arg-type]


def test_is_retryable_rejects_non_error_category_argument() -> None:
    with pytest.raises(ProviderContractValidationError):
        DEFAULT_RETRY_POLICY.is_retryable("timeout")  # type: ignore[arg-type]


def test_retry_policy_is_frozen() -> None:
    policy = AIProviderRetryPolicy()
    with pytest.raises(AttributeError):
        policy.maximum_attempts = 5  # type: ignore[misc]
