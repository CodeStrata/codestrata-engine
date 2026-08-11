"""Safe availability-flags diagnostic view of a provider usage record.

``ProviderUsageMetadata`` never carries prompts, responses, credentials, or
cost/pricing data in the first place (see ``usage_policy.
FORBIDDEN_USAGE_FIELD_NAMES``), so unlike ``diagnostics.py``/
``execution_diagnostics.py`` there is nothing to redact. This module instead
offers an *availability* view — which fields a provider actually populated —
useful for a future diagnostics/telemetry surface that wants to know "did
this provider report token counts?" without depending on exact values.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata


def usage_availability_view(usage: ProviderUsageMetadata) -> dict[str, Any]:
    """Return which usage fields are present, without the values themselves."""

    return {
        "has_completion_status": usage.completion_status is not None,
        "has_input_tokens": usage.input_tokens is not None,
        "has_latency_ms": usage.latency_ms is not None,
        "has_output_tokens": usage.output_tokens is not None,
        "has_request_count": usage.request_count is not None,
        "has_retry_count": usage.retry_count is not None,
        "has_total_tokens": usage.total_tokens is not None,
    }


__all__ = ["usage_availability_view"]
