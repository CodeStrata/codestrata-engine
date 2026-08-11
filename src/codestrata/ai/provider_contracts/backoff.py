"""Deterministic, bounded backoff-delay computation. Never sleeps.

Three strategies: ``none`` (always zero delay), ``fixed`` (a constant
delay), and ``exponential`` (``base_delay_seconds * multiplier **
(attempt - 1)``, capped at ``max_delay_seconds``). ``jitter`` is disabled by
default so delay computation stays fully deterministic; when enabled, the
jitter factor is derived only from ``attempt`` (via a seeded
``random.Random``), never from wall-clock time or any other non-deterministic
source, so the result stays reproducible given the same inputs.

Nothing here calls ``time.sleep`` — see ``executor.py`` for where the
computed delay is handed to an injected ``sleeper`` callable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution_policy import ALLOWED_BACKOFF_STRATEGIES

_JITTER_FRACTION = 0.1


class BackoffStrategy(StrEnum):
    """Bounded, closed set of supported backoff strategies."""

    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


assert tuple(s.value for s in BackoffStrategy) == ALLOWED_BACKOFF_STRATEGIES, (
    "BackoffStrategy enum values must exactly match execution_policy.ALLOWED_BACKOFF_STRATEGIES"
)


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    """A bounded, deterministic backoff declaration. Never sleeps by itself."""

    strategy: BackoffStrategy = BackoffStrategy.NONE
    base_delay_seconds: float = 0.0
    multiplier: float = 2.0
    max_delay_seconds: float = 30.0
    jitter: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, BackoffStrategy):
            raise ProviderContractValidationError(
                f"strategy must be a BackoffStrategy, got {type(self.strategy).__name__}"
            )
        for field_name, value in (
            ("base_delay_seconds", self.base_delay_seconds),
            ("multiplier", self.multiplier),
            ("max_delay_seconds", self.max_delay_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProviderContractValidationError(f"{field_name} must be a number")
        if self.base_delay_seconds < 0:
            raise ProviderContractValidationError("base_delay_seconds must be non-negative")
        if self.multiplier <= 0:
            raise ProviderContractValidationError("multiplier must be positive")
        if self.max_delay_seconds < 0:
            raise ProviderContractValidationError("max_delay_seconds must be non-negative")
        if not isinstance(self.jitter, bool):
            raise ProviderContractValidationError("jitter must be a bool")


def compute_backoff_delay(policy: BackoffPolicy, attempt: int) -> float:
    """Return the delay (seconds) to wait after ``attempt`` (1-indexed) failed.

    Pure and deterministic for a given ``(policy, attempt)`` pair (including
    when ``policy.jitter`` is enabled). Never sleeps.
    """

    if not isinstance(policy, BackoffPolicy):
        raise ProviderContractValidationError("policy must be a BackoffPolicy")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ProviderContractValidationError("attempt must be a positive int")

    if policy.strategy is BackoffStrategy.NONE:
        delay = 0.0
    elif policy.strategy is BackoffStrategy.FIXED:
        delay = policy.base_delay_seconds
    else:
        delay = policy.base_delay_seconds * (policy.multiplier ** (attempt - 1))

    delay = min(delay, policy.max_delay_seconds)

    if policy.jitter and delay > 0:
        rng = random.Random(attempt)
        factor = 1.0 + rng.uniform(-_JITTER_FRACTION, _JITTER_FRACTION)
        delay = max(0.0, delay * factor)

    return delay


DEFAULT_BACKOFF_POLICY = BackoffPolicy()


__all__ = [
    "DEFAULT_BACKOFF_POLICY",
    "BackoffPolicy",
    "BackoffStrategy",
    "compute_backoff_delay",
]
