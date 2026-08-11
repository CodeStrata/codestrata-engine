"""``AIProviderRetryPolicy``: bounded, unwired retry-attempt policy.

``maximum_attempts`` is the canonical field name and always includes the
first (non-retry) attempt — a policy with ``maximum_attempts=1`` makes
exactly one call and never retries. ``max_retries_to_maximum_attempts()``
converts the *settings*-shaped ``max_retries`` field (which counts retries
only, excluding the first attempt — see ``BedrockAdapterConfiguration.
max_retries`` / ``OpenAIAdapterConfiguration.max_retries`` from Slice 11.3)
into this package's canonical ``maximum_attempts``.

Two ready-made policies are provided:

* ``DEFAULT_RETRY_POLICY`` (``maximum_attempts=1``) — matches CR-1's
  existing "exactly one ``AIProvider.execute()`` call per assess run"
  behavior. This is what ``AIProviderExecutor`` uses by default.
* ``SETTINGS_REPRESENTABLE_RETRY_POLICY`` — a *pure representation* of what
  ``BedrockSettings.max_retries`` / ``OpenAISettings.max_retries``'s
  default value (``3``) would mean if it were ever wired up
  (``maximum_attempts=4``). Building this value object activates nothing:
  no executor uses it by default, and nothing reads the real settings value
  to construct it — it is built from
  ``execution_policy.SETTINGS_DEFAULT_MAX_RETRIES``, a hand-restated
  literal that the verification suite cross-checks against the real
  settings defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ErrorCategory, ProviderContractValidationError
from codestrata.ai.provider_contracts.execution_policy import (
    DEFAULT_MAXIMUM_ATTEMPTS,
    DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES,
    DEFAULT_RETRYABLE_ERROR_CATEGORIES,
    MAX_MAXIMUM_ATTEMPTS,
    SETTINGS_DEFAULT_MAX_RETRIES,
)

DEFAULT_RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    ErrorCategory(value) for value in DEFAULT_RETRYABLE_ERROR_CATEGORIES
)
DEFAULT_NON_RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    ErrorCategory(value) for value in DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES
)


def max_retries_to_maximum_attempts(max_retries: int) -> int:
    """Convert a settings-shaped ``max_retries`` (retries only) to ``maximum_attempts``."""

    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise ProviderContractValidationError("max_retries must be an int")
    if max_retries < 0:
        raise ProviderContractValidationError("max_retries must be non-negative")
    return max_retries + 1


@dataclass(frozen=True, slots=True)
class AIProviderRetryPolicy:
    """Bounded, unwired retry policy. ``maximum_attempts`` includes the first attempt."""

    maximum_attempts: int = DEFAULT_MAXIMUM_ATTEMPTS
    retryable_categories: frozenset[ErrorCategory] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_CATEGORIES
    )
    source_category: SourceCategory | None = None

    def __post_init__(self) -> None:
        if isinstance(self.maximum_attempts, bool) or not isinstance(self.maximum_attempts, int):
            raise ProviderContractValidationError("maximum_attempts must be an int")
        if not (1 <= self.maximum_attempts <= MAX_MAXIMUM_ATTEMPTS):
            raise ProviderContractValidationError(
                f"maximum_attempts must be within [1, {MAX_MAXIMUM_ATTEMPTS}]"
            )
        if not isinstance(self.retryable_categories, frozenset) or not all(
            isinstance(item, ErrorCategory) for item in self.retryable_categories
        ):
            raise ProviderContractValidationError(
                "retryable_categories must be a frozenset of ErrorCategory"
            )
        if self.source_category is not None and not isinstance(
            self.source_category, SourceCategory
        ):
            raise ProviderContractValidationError(
                "source_category must be a SourceCategory or None, got "
                f"{type(self.source_category).__name__}"
            )

    def is_retryable(self, category: ErrorCategory) -> bool:
        if not isinstance(category, ErrorCategory):
            raise ProviderContractValidationError(
                f"category must be an ErrorCategory, got {type(category).__name__}"
            )
        return category in self.retryable_categories


DEFAULT_RETRY_POLICY = AIProviderRetryPolicy(maximum_attempts=DEFAULT_MAXIMUM_ATTEMPTS)

# A pure *representation* of what BedrockSettings.max_retries/OpenAISettings.
# max_retries's default (3) would mean as maximum_attempts (4) — see module
# docstring. Not the default used by AIProviderExecutor; nothing reads real
# settings to build this, and constructing it does not activate anything.
SETTINGS_REPRESENTABLE_RETRY_POLICY = AIProviderRetryPolicy(
    maximum_attempts=max_retries_to_maximum_attempts(SETTINGS_DEFAULT_MAX_RETRIES)
)

MAXIMUM_ATTEMPTS_CEILING = MAX_MAXIMUM_ATTEMPTS


__all__ = [
    "DEFAULT_NON_RETRYABLE_CATEGORIES",
    "DEFAULT_RETRYABLE_CATEGORIES",
    "DEFAULT_RETRY_POLICY",
    "MAXIMUM_ATTEMPTS_CEILING",
    "SETTINGS_REPRESENTABLE_RETRY_POLICY",
    "AIProviderRetryPolicy",
    "max_retries_to_maximum_attempts",
]
