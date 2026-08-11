"""Tests for the pure, sleep-free ``decide_retry``/``RetryDecision``."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.backoff import BackoffPolicy, BackoffStrategy
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.retry_decision import (
    REASON_CATEGORY_NOT_RETRYABLE,
    REASON_MAXIMUM_ATTEMPTS_REACHED,
    REASON_RETRY_SCHEDULED,
    RetryDecision,
    decide_retry,
)
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy

_FIXED_BACKOFF = BackoffPolicy(strategy=BackoffStrategy.FIXED, base_delay_seconds=1.5)
_NONE_BACKOFF = BackoffPolicy()


def test_decide_retry_is_terminal_when_maximum_attempts_reached() -> None:
    decision = decide_retry(
        attempt=1,
        category=ErrorCategory.TIMEOUT,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=1),
        backoff_policy=_NONE_BACKOFF,
    )
    assert decision.should_retry is False
    assert decision.terminal is True
    assert decision.delay_seconds == 0.0
    assert decision.next_attempt == 1
    assert decision.reason_code == REASON_MAXIMUM_ATTEMPTS_REACHED


def test_decide_retry_is_terminal_when_category_not_retryable() -> None:
    decision = decide_retry(
        attempt=1,
        category=ErrorCategory.INVALID_REQUEST,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
        backoff_policy=_NONE_BACKOFF,
    )
    assert decision.should_retry is False
    assert decision.terminal is True
    assert decision.reason_code == REASON_CATEGORY_NOT_RETRYABLE


def test_decide_retry_schedules_a_retry_for_a_retryable_category_within_budget() -> None:
    decision = decide_retry(
        attempt=1,
        category=ErrorCategory.TIMEOUT,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=3),
        backoff_policy=_FIXED_BACKOFF,
    )
    assert decision.should_retry is True
    assert decision.terminal is False
    assert decision.next_attempt == 2
    assert decision.delay_seconds == 1.5
    assert decision.reason_code == REASON_RETRY_SCHEDULED


def test_decide_retry_never_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("decide_retry must never sleep")

    monkeypatch.setattr(time, "sleep", _fail_if_called)
    decide_retry(
        attempt=1,
        category=ErrorCategory.TIMEOUT,
        retry_policy=AIProviderRetryPolicy(maximum_attempts=5),
        backoff_policy=_FIXED_BACKOFF,
    )


def test_decide_retry_rejects_non_positive_attempt() -> None:
    with pytest.raises(ProviderContractValidationError):
        decide_retry(
            attempt=0,
            category=ErrorCategory.TIMEOUT,
            retry_policy=AIProviderRetryPolicy(),
            backoff_policy=_NONE_BACKOFF,
        )


def test_decide_retry_rejects_invalid_category() -> None:
    with pytest.raises(ProviderContractValidationError):
        decide_retry(
            attempt=1,
            category="timeout",  # type: ignore[arg-type]
            retry_policy=AIProviderRetryPolicy(),
            backoff_policy=_NONE_BACKOFF,
        )


def test_decide_retry_rejects_invalid_retry_policy() -> None:
    with pytest.raises(ProviderContractValidationError):
        decide_retry(
            attempt=1,
            category=ErrorCategory.TIMEOUT,
            retry_policy="not-a-policy",  # type: ignore[arg-type]
            backoff_policy=_NONE_BACKOFF,
        )


def test_decide_retry_rejects_invalid_backoff_policy() -> None:
    with pytest.raises(ProviderContractValidationError):
        decide_retry(
            attempt=1,
            category=ErrorCategory.TIMEOUT,
            retry_policy=AIProviderRetryPolicy(),
            backoff_policy="not-a-policy",  # type: ignore[arg-type]
        )


def test_retry_decision_rejects_should_retry_and_terminal_both_true() -> None:
    with pytest.raises(ProviderContractValidationError):
        RetryDecision(
            should_retry=True,
            next_attempt=2,
            delay_seconds=0.0,
            reason_code="x",
            terminal=True,
        )


def test_retry_decision_rejects_non_terminal_non_retry_decision() -> None:
    with pytest.raises(ProviderContractValidationError):
        RetryDecision(
            should_retry=False,
            next_attempt=1,
            delay_seconds=0.0,
            reason_code="x",
            terminal=False,
        )


def test_retry_decision_rejects_terminal_with_nonzero_delay() -> None:
    with pytest.raises(ProviderContractValidationError):
        RetryDecision(
            should_retry=False,
            next_attempt=1,
            delay_seconds=1.0,
            reason_code="x",
            terminal=True,
        )


def test_retry_decision_rejects_negative_delay() -> None:
    with pytest.raises(ProviderContractValidationError):
        RetryDecision(
            should_retry=True,
            next_attempt=2,
            delay_seconds=-1.0,
            reason_code="x",
            terminal=False,
        )


def test_retry_decision_rejects_empty_reason_code() -> None:
    with pytest.raises(ProviderContractValidationError):
        RetryDecision(
            should_retry=False,
            next_attempt=1,
            delay_seconds=0.0,
            reason_code="",
            terminal=True,
        )
