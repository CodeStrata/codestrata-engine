"""Map Bedrock Converse usage/metrics fields onto ``ProviderUsageMetadata``.

The wire fields are the same the pre-migration provider read from the
Converse response's ``usage`` mapping: ``inputTokens`` -> ``input_tokens``,
``outputTokens`` -> ``output_tokens``, ``totalTokens`` -> ``total_tokens``.
Anything missing, non-numeric, or negative becomes ``None``, exactly as
before. When ``totalTokens`` is absent but both halves are present, the total
is **derived** as their sum — also exactly as before.

``ProviderUsageMetadata`` additionally enforces ``total_tokens ==
input_tokens + output_tokens`` when all three are present. A service that
reports an inconsistent triple would make that constructor raise, so this
module drops ``total_tokens`` in that case and reports it via
:attr:`MappedUsage.total_tokens_dropped`. The *legacy* ``ModelUsage`` on
``ModelInvocationMetadata`` is built from :attr:`MappedUsage.raw_totals`
instead, which keeps the reported (or derived) triple verbatim — so migrating
to this contract type cannot change what a report records.

Latency comes from ``metrics.latencyMs`` when the service reports a usable
non-negative number, and from the adapter's wall-clock measurement
otherwise. That preference order is the pre-migration behavior.

No cost, pricing, billing, prompt, response, or request-ID field is ever
produced here (see ``usage_policy.FORBIDDEN_USAGE_FIELD_NAMES``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus

INPUT_TOKENS_FIELD = "inputTokens"
OUTPUT_TOKENS_FIELD = "outputTokens"
TOTAL_TOKENS_FIELD = "totalTokens"
LATENCY_MS_FIELD = "latencyMs"


@dataclass(frozen=True, slots=True)
class RawTokenTotals:
    """The reported token triple, normalized to optional non-negative ints."""

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
    """A validated contract usage record plus the verbatim reported totals."""

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


def extract_raw_totals(usage_payload: Any) -> RawTokenTotals:
    """Read the three token fields off a Converse ``usage`` mapping (or ``None``).

    Derives ``total_tokens`` from the two halves when the service omitted it,
    matching the pre-migration ``bedrock._extract_usage``.
    """

    if not isinstance(usage_payload, dict):
        return RawTokenTotals()
    input_tokens = optional_non_negative_int(usage_payload.get(INPUT_TOKENS_FIELD))
    output_tokens = optional_non_negative_int(usage_payload.get(OUTPUT_TOKENS_FIELD))
    total_tokens = optional_non_negative_int(usage_payload.get(TOTAL_TOKENS_FIELD))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return RawTokenTotals(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def extract_reported_latency_ms(metrics_payload: Any) -> float | None:
    """Read ``metrics.latencyMs`` off a Converse response, or ``None``."""

    if not isinstance(metrics_payload, dict):
        return None
    value = metrics_payload.get(LATENCY_MS_FIELD)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def resolve_latency_ms(
    *, reported_latency_ms: float | None, measured_latency_ms: float
) -> float:
    """Prefer the service-reported latency, falling back to the wall-clock measurement."""

    if reported_latency_ms is not None:
        return float(reported_latency_ms)
    return max(0.0, float(measured_latency_ms))


def map_usage(
    usage_payload: Any,
    *,
    latency_ms: float,
    completion_status: UsageCompletionStatus,
    request_count: int = 1,
    retry_count: int = 0,
) -> MappedUsage:
    """Map a Converse ``usage`` mapping onto a validated ``ProviderUsageMetadata``."""

    raw = extract_raw_totals(usage_payload)
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
    "INPUT_TOKENS_FIELD",
    "LATENCY_MS_FIELD",
    "OUTPUT_TOKENS_FIELD",
    "TOTAL_TOKENS_FIELD",
    "MappedUsage",
    "RawTokenTotals",
    "extract_raw_totals",
    "extract_reported_latency_ms",
    "failure_usage",
    "map_usage",
    "optional_non_negative_int",
    "resolve_latency_ms",
]
