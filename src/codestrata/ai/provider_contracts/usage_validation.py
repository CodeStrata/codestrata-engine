"""Standalone validation helpers for provider usage records.

Wraps/duplicates the same invariants ``ProviderUsageMetadata.__post_init__``
already enforces (see ``usage.py`` and the shared helpers in
``validation.py``), exposed standalone for callers/tests that want to
validate already-extracted usage fields before constructing an instance.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_policy import ALLOWED_USAGE_COMPLETION_STATUSES
from codestrata.ai.provider_contracts.validation import (
    validate_non_negative,
    validate_usage_token_consistency,
)


def validate_completion_status_is_known(value: str) -> None:
    """Reject any completion-status string outside the closed, policy-bounded set."""

    if not isinstance(value, str) or value not in ALLOWED_USAGE_COMPLETION_STATUSES:
        raise ProviderContractValidationError(
            f"unknown completion_status {value!r}; allowed: {ALLOWED_USAGE_COMPLETION_STATUSES}"
        )


def validate_usage_metadata(usage: ProviderUsageMetadata) -> None:
    """Re-validate an already-constructed ``ProviderUsageMetadata``.

    ``ProviderUsageMetadata.__post_init__`` already enforces every one of
    these invariants at construction time; this function exists for callers
    (and the verification suite) that want to re-check a usage record
    obtained from elsewhere without relying on ``__post_init__`` having run
    with today's rules.
    """

    if not isinstance(usage, ProviderUsageMetadata):
        raise ProviderContractValidationError(
            "validate_usage_metadata() requires a ProviderUsageMetadata"
        )
    integer_field_names = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "request_count",
        "retry_count",
    )
    for field_name in integer_field_names:
        validate_non_negative(getattr(usage, field_name), field_name=field_name)
    validate_non_negative(usage.latency_ms, field_name="latency_ms")
    validate_usage_token_consistency(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
    )
    if usage.completion_status is not None:
        if not isinstance(usage.completion_status, UsageCompletionStatus):
            raise ProviderContractValidationError(
                "completion_status must be a UsageCompletionStatus"
            )
        validate_completion_status_is_known(usage.completion_status.value)


__all__ = [
    "validate_completion_status_is_known",
    "validate_usage_metadata",
]
