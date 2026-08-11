"""Tests for ``BackoffPolicy``/``compute_backoff_delay``. All computation must be sleep-free."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.backoff import (
    DEFAULT_BACKOFF_POLICY,
    BackoffPolicy,
    BackoffStrategy,
    compute_backoff_delay,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError


def test_default_backoff_policy_is_none_strategy_zero_delay() -> None:
    assert DEFAULT_BACKOFF_POLICY.strategy is BackoffStrategy.NONE
    assert compute_backoff_delay(DEFAULT_BACKOFF_POLICY, 1) == 0.0


def test_none_strategy_always_returns_zero_regardless_of_attempt() -> None:
    policy = BackoffPolicy(strategy=BackoffStrategy.NONE)
    assert compute_backoff_delay(policy, 1) == 0.0
    assert compute_backoff_delay(policy, 10) == 0.0


def test_fixed_strategy_returns_a_constant_delay() -> None:
    policy = BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=2.0)
    assert compute_backoff_delay(policy, 1) == 2.0
    assert compute_backoff_delay(policy, 5) == 2.0


def test_exponential_strategy_grows_with_attempt() -> None:
    policy = BackoffPolicy(
        strategy=BackoffStrategy.EXPONENTIAL,
        base_delay_seconds=1.0,
        multiplier=2.0,
        max_delay_seconds=100.0,
    )
    assert compute_backoff_delay(policy, 1) == 1.0
    assert compute_backoff_delay(policy, 2) == 2.0
    assert compute_backoff_delay(policy, 3) == 4.0


def test_exponential_strategy_is_capped_at_max_delay_seconds() -> None:
    policy = BackoffPolicy(
        strategy=BackoffStrategy.EXPONENTIAL,
        base_delay_seconds=1.0,
        multiplier=10.0,
        max_delay_seconds=5.0,
    )
    assert compute_backoff_delay(policy, 5) == 5.0


def test_jitter_disabled_by_default_and_deterministic_without_it() -> None:
    policy = BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=3.0)
    assert policy.jitter is False
    assert compute_backoff_delay(policy, 2) == compute_backoff_delay(policy, 2)


def test_jitter_when_enabled_is_still_deterministic_for_the_same_attempt() -> None:
    policy = BackoffPolicy(
        strategy=BackoffStrategy.FIXED, base_delay_seconds=10.0, jitter=True
    )
    first = compute_backoff_delay(policy, 3)
    second = compute_backoff_delay(policy, 3)
    assert first == second
    assert 9.0 <= first <= 11.0


def test_jitter_never_produces_a_negative_delay() -> None:
    policy = BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=0.05, jitter=True)
    for attempt in range(1, 50):
        assert compute_backoff_delay(policy, attempt) >= 0.0


def test_compute_backoff_delay_rejects_non_positive_attempt() -> None:
    with pytest.raises(ProviderContractValidationError):
        compute_backoff_delay(DEFAULT_BACKOFF_POLICY, 0)
    with pytest.raises(ProviderContractValidationError):
        compute_backoff_delay(DEFAULT_BACKOFF_POLICY, -1)


def test_compute_backoff_delay_rejects_bool_attempt() -> None:
    with pytest.raises(ProviderContractValidationError):
        compute_backoff_delay(DEFAULT_BACKOFF_POLICY, True)  # type: ignore[arg-type]


def test_compute_backoff_delay_rejects_non_backoff_policy() -> None:
    with pytest.raises(ProviderContractValidationError):
        compute_backoff_delay("not-a-policy", 1)  # type: ignore[arg-type]


def test_backoff_policy_rejects_negative_base_delay() -> None:
    with pytest.raises(ProviderContractValidationError):
        BackoffPolicy(base_delay_seconds=-1.0)


def test_backoff_policy_rejects_non_positive_multiplier() -> None:
    with pytest.raises(ProviderContractValidationError):
        BackoffPolicy(multiplier=0.0)
    with pytest.raises(ProviderContractValidationError):
        BackoffPolicy(multiplier=-1.0)


def test_backoff_policy_rejects_negative_max_delay() -> None:
    with pytest.raises(ProviderContractValidationError):
        BackoffPolicy(max_delay_seconds=-1.0)


def test_backoff_policy_rejects_invalid_strategy() -> None:
    with pytest.raises(ProviderContractValidationError):
        BackoffPolicy(strategy="fixed")  # type: ignore[arg-type]


def test_backoff_policy_rejects_non_bool_jitter() -> None:
    with pytest.raises(ProviderContractValidationError):
        BackoffPolicy(jitter="yes")  # type: ignore[arg-type]


def test_backoff_policy_is_frozen() -> None:
    policy = BackoffPolicy()
    with pytest.raises(AttributeError):
        policy.strategy = BackoffStrategy.FIXED  # type: ignore[misc]
