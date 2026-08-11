"""Deterministic JSON serialization: private vs. diagnostic usage record views.

Unlike ``serialization.py``/``configuration_serialization.py``/
``execution_serialization.py``, the private and diagnostic views here are
**identical** in content: ``ProviderUsageMetadata`` never carries a prompt,
a response, a credential, a filesystem path, or cost/pricing/billing data in
the first place (see ``usage_policy.FORBIDDEN_USAGE_FIELD_NAMES``), so there
is nothing for the "diagnostic" view to redact relative to the "private"
one. Both functions are kept as separate, named entry points anyway so
callers depend on a stable, documented name rather than assuming "usage is
always fully safe to log" without an explicit function boundary to enforce
it if a future field ever needed different treatment.
"""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def usage_view(usage: ProviderUsageMetadata) -> dict[str, Any]:
    """Return the complete, field-for-field view of a usage record.

    Safe to log/report in full: every field is a token count, a latency
    measurement, a retry/request count, or a bounded completion-status
    string.
    """

    return {
        "completion_status": (
            str(usage.completion_status) if usage.completion_status is not None else None
        ),
        "input_tokens": usage.input_tokens,
        "latency_ms": usage.latency_ms,
        "output_tokens": usage.output_tokens,
        "request_count": usage.request_count,
        "retry_count": usage.retry_count,
        "total_tokens": usage.total_tokens,
    }


def private_view_of_usage(usage: ProviderUsageMetadata) -> dict[str, Any]:
    """Return the internal usage view (identical to :func:`diagnostic_view_of_usage`)."""

    return usage_view(usage)


def diagnostic_view_of_usage(usage: ProviderUsageMetadata) -> dict[str, Any]:
    """Return the safe-to-report usage view (identical to :func:`private_view_of_usage`)."""

    return usage_view(usage)


def serialize_usage_for_diagnostics(usage: ProviderUsageMetadata) -> str:
    """Canonical JSON of the diagnostic view of a usage record."""

    return canonical_json(diagnostic_view_of_usage(usage))


def serialize_usage_private(usage: ProviderUsageMetadata) -> str:
    """Canonical JSON of the private (identical) view of a usage record."""

    return canonical_json(private_view_of_usage(usage))


__all__ = [
    "canonical_json",
    "diagnostic_view_of_usage",
    "private_view_of_usage",
    "serialize_usage_for_diagnostics",
    "serialize_usage_private",
    "usage_view",
]
