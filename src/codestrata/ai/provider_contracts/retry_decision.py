"""Pure, sleep-free retry decision-making.

``decide_retry`` is a plain function of its arguments: given the attempt
number that just failed, the failure's bounded ``ErrorCategory``, a retry
policy, and a backoff policy, it returns a ``RetryDecision`` describing
whether to retry, the next attempt number, and how long to wait first. It
never calls ``time.sleep`` — see ``executor.py`` for where the computed
delay is handed to an injected ``sleeper`` callable.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.backoff import BackoffPolicy, compute_backoff_delay
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.retry_policy import AIProviderRetryPolicy

REASON_MAXIMUM_ATTEMPTS_REACHED = "maximum_attempts_reached"
REASON_CATEGORY_NOT_RETRYABLE = "error_category_not_retryable"
REASON_RETRY_SCHEDULED = "retryable_category_within_attempt_budget"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """The outcome of a single retry decision. Never itself sleeps."""

    should_retry: bool
    next_attempt: int
    delay_seconds: float
    reason_code: str
    terminal: bool

    def __post_init__(self) -> None:
        if not isinstance(self.should_retry, bool):
            raise ProviderContractValidationError("should_retry must be a bool")
        if (
            isinstance(self.next_attempt, bool)
            or not isinstance(self.next_attempt, int)
            or self.next_attempt < 1
        ):
            raise ProviderContractValidationError("next_attempt must be a positive int")
        if (
            isinstance(self.delay_seconds, bool)
            or not isinstance(self.delay_seconds, (int, float))
            or self.delay_seconds < 0
        ):
            raise ProviderContractValidationError("delay_seconds must be a non-negative number")
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ProviderContractValidationError("reason_code must be a non-empty string")
        if not isinstance(self.terminal, bool):
            raise ProviderContractValidationError("terminal must be a bool")
        if self.should_retry and self.terminal:
            raise ProviderContractValidationError(
                "a should_retry decision cannot also be terminal"
            )
        if not self.should_retry and not self.terminal:
            raise ProviderContractValidationError(
                "a decision that does not retry must be terminal"
            )
        if not self.should_retry and self.delay_seconds != 0:
            raise ProviderContractValidationError(
                "a decision that does not retry must have delay_seconds == 0"
            )


def decide_retry(
    *,
    attempt: int,
    category: ErrorCategory,
    retry_policy: AIProviderRetryPolicy,
    backoff_policy: BackoffPolicy,
) -> RetryDecision:
    """Decide, given that ``attempt`` (1-indexed) just failed with ``category``, whether to retry.

    Pure: never sleeps, never reads a clock, never mutates its arguments.
    """

    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ProviderContractValidationError("attempt must be a positive int")
    if not isinstance(category, ErrorCategory):
        raise ProviderContractValidationError(
            f"category must be an ErrorCategory, got {type(category).__name__}"
        )
    if not isinstance(retry_policy, AIProviderRetryPolicy):
        raise ProviderContractValidationError("retry_policy must be an AIProviderRetryPolicy")
    if not isinstance(backoff_policy, BackoffPolicy):
        raise ProviderContractValidationError("backoff_policy must be a BackoffPolicy")

    if attempt >= retry_policy.maximum_attempts:
        return RetryDecision(
            should_retry=False,
            next_attempt=attempt,
            delay_seconds=0.0,
            reason_code=REASON_MAXIMUM_ATTEMPTS_REACHED,
            terminal=True,
        )
    if not retry_policy.is_retryable(category):
        return RetryDecision(
            should_retry=False,
            next_attempt=attempt,
            delay_seconds=0.0,
            reason_code=REASON_CATEGORY_NOT_RETRYABLE,
            terminal=True,
        )
    delay = compute_backoff_delay(backoff_policy, attempt)
    return RetryDecision(
        should_retry=True,
        next_attempt=attempt + 1,
        delay_seconds=delay,
        reason_code=REASON_RETRY_SCHEDULED,
        terminal=False,
    )


__all__ = [
    "REASON_CATEGORY_NOT_RETRYABLE",
    "REASON_MAXIMUM_ATTEMPTS_REACHED",
    "REASON_RETRY_SCHEDULED",
    "RetryDecision",
    "decide_retry",
]
