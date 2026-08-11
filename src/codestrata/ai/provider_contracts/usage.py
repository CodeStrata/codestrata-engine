"""Optional, validated token/latency/retry/completion-status usage metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.usage_policy import ALLOWED_USAGE_COMPLETION_STATUSES

_NON_NEGATIVE_INT_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "request_count",
    "retry_count",
)


class UsageCompletionStatus(StrEnum):
    """Coarse outcome the usage measurement was taken for.

    Bounded enum values aligned with ``execution.ProviderExecutionStatus``
    (Slice 11.4) — see ``usage_policy.py``'s module docstring for why the two
    vocabularies are kept in lockstep. This slice does not import
    ``execution.py`` (usage.py has zero ``codestrata`` dependencies outside
    ``errors.py``/``usage_policy.py``, matching the rest of this package's
    dependency-boundary discipline); the alignment is enforced by the
    ``assert`` below and cross-checked for real by the verification suite.
    """

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SKIPPED = "skipped"


_ACTUAL_USAGE_COMPLETION_STATUSES = tuple(status.value for status in UsageCompletionStatus)
assert _ACTUAL_USAGE_COMPLETION_STATUSES == ALLOWED_USAGE_COMPLETION_STATUSES, (
    "UsageCompletionStatus enum values must exactly match "
    "usage_policy.ALLOWED_USAGE_COMPLETION_STATUSES"
)


@dataclass(frozen=True, slots=True)
class ProviderUsageMetadata:
    """Optional usage metadata for a single provider execution.

    All fields are optional (a fake/unavailable provider may report none of
    them). When present, integer fields must be non-negative and
    ``latency_ms`` must be non-negative. When ``input_tokens``,
    ``output_tokens``, and ``total_tokens`` are *all* present, ``total_tokens``
    must equal their sum; when any of the three is absent, no cross-field
    consistency is enforced (a provider may report only a subset).

    ``completion_status``, added in Slice 11.5, is an optional
    ``UsageCompletionStatus`` describing what happened during the call this
    usage was measured for. It carries no cost, pricing, billing, prompt,
    response, request-ID, or exception-text information — those are
    permanently out of scope for this type (see ``usage_policy.
    FORBIDDEN_USAGE_FIELD_NAMES``).
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    request_count: int | None = None
    retry_count: int | None = None
    completion_status: UsageCompletionStatus | None = None

    def __post_init__(self) -> None:
        for field_name in _NON_NEGATIVE_INT_FIELDS:
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ProviderContractValidationError(f"{field_name} must be non-negative")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ProviderContractValidationError("latency_ms must be non-negative")
        if (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ProviderContractValidationError(
                "total_tokens must equal input_tokens + output_tokens when all three are present"
            )
        if self.completion_status is not None and not isinstance(
            self.completion_status, UsageCompletionStatus
        ):
            raise ProviderContractValidationError(
                "completion_status must be a UsageCompletionStatus"
            )


__all__ = ["ProviderUsageMetadata", "UsageCompletionStatus"]
