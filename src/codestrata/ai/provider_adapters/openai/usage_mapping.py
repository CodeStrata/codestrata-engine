"""Map OpenAI usage fields onto ``ProviderUsageMetadata``.

The wire fields are the same three the pre-migration provider read:
``prompt_tokens`` -> ``input_tokens``, ``completion_tokens`` ->
``output_tokens``, ``total_tokens`` -> ``total_tokens``. Anything missing,
non-numeric, or negative becomes ``None``, exactly as before.

``ProviderUsageMetadata`` additionally enforces ``total_tokens ==
input_tokens + output_tokens`` when all three are present. A provider that
reports an inconsistent triple would make that constructor raise, so this
module drops ``total_tokens`` in that case and reports it via
:attr:`MappedUsage.total_tokens_dropped`. The *legacy* ``ModelUsage`` on
``ModelInvocationMetadata`` is built from :attr:`MappedUsage.raw_totals`
instead, which keeps the provider-reported triple verbatim — so migrating to
this contract type cannot change what a report records.

No cost, pricing, billing, prompt, response, or request-ID field is ever
produced here (see ``usage_policy.FORBIDDEN_USAGE_FIELD_NAMES``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus

PROMPT_TOKENS_FIELD = "prompt_tokens"
COMPLETION_TOKENS_FIELD = "completion_tokens"
TOTAL_TOKENS_FIELD = "total_tokens"


@dataclass(frozen=True, slots=True)
class RawTokenTotals:
    """The provider-reported token triple, normalized to optional non-negative ints."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def consistent(self) -> bool:
        """Return whether the triple is either incomplete or internally consistent."""

        if self.input_tokens is None or self.output_tokens is None or self.total_tokens is None:
            return True
        return self.total_tokens == self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class MappedUsage:
    """A validated contract usage record plus the verbatim provider-reported totals."""

    usage: ProviderUsageMetadata
    raw_totals: RawTokenTotals
    total_tokens_dropped: bool = False


def optional_non_negative_int(value: Any) -> int | None:
    """Coerce ``value`` to a non-negative int, or ``None`` when that is not possible."""

    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def extract_raw_totals(usage_object: Any) -> RawTokenTotals:
    """Read the three token fields off an SDK usage object (or ``None``)."""

    return RawTokenTotals(
        input_tokens=optional_non_negative_int(getattr(usage_object, PROMPT_TOKENS_FIELD, None)),
        output_tokens=optional_non_negative_int(
            getattr(usage_object, COMPLETION_TOKENS_FIELD, None)
        ),
        total_tokens=optional_non_negative_int(getattr(usage_object, TOTAL_TOKENS_FIELD, None)),
    )


def map_usage(
    usage_object: Any,
    *,
    latency_ms: float,
    completion_status: UsageCompletionStatus,
    request_count: int = 1,
    retry_count: int = 0,
) -> MappedUsage:
    """Map an SDK usage object onto a validated ``ProviderUsageMetadata``."""

    raw = extract_raw_totals(usage_object)
    total_tokens = raw.total_tokens
    dropped = False
    if not raw.consistent:
        total_tokens = None
        dropped = True
    usage = ProviderUsageMetadata(
        input_tokens=raw.input_tokens,
        output_tokens=raw.output_tokens,
        total_tokens=total_tokens,
        latency_ms=max(0.0, float(latency_ms)),
        request_count=request_count,
        retry_count=retry_count,
        completion_status=completion_status,
    )
    return MappedUsage(usage=usage, raw_totals=raw, total_tokens_dropped=dropped)


def failure_usage(
    *,
    latency_ms: float,
    completion_status: UsageCompletionStatus,
    request_count: int = 1,
    retry_count: int = 0,
) -> ProviderUsageMetadata:
    """Build a token-free usage record for an attempt that produced no usage data."""

    return ProviderUsageMetadata(
        latency_ms=max(0.0, float(latency_ms)),
        request_count=request_count,
        retry_count=retry_count,
        completion_status=completion_status,
    )


__all__ = [
    "COMPLETION_TOKENS_FIELD",
    "PROMPT_TOKENS_FIELD",
    "TOTAL_TOKENS_FIELD",
    "MappedUsage",
    "RawTokenTotals",
    "extract_raw_totals",
    "failure_usage",
    "map_usage",
    "optional_non_negative_int",
]
