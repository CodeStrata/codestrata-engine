"""Safe, privacy-preserving diagnostic views of an ``AIProviderExecutionResult``.

Mirrors ``diagnostics.py`` (Slice 11.2) and ``configuration_diagnostics.py``
(Slice 11.3). Never includes ``provider_result.content`` (prompt/response
text or structured payload) — the nested ``provider_result`` view reuses
``diagnostics.diagnostic_view_of_result``, which already excludes it.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.diagnostics import diagnostic_view_of_result
from codestrata.ai.provider_contracts.execution_models import AIProviderExecutionResult


def diagnostic_view_of_execution_result(result: AIProviderExecutionResult) -> dict[str, Any]:
    """Return a safe, content-free summary of an execution result."""

    return {
        "attempts": result.attempts,
        "capability": str(result.capability),
        "diagnostics": {
            "attempt_error_categories": list(result.diagnostics.attempt_error_categories),
            "backoff_strategy": result.diagnostics.backoff_strategy,
            "retry_policy_maximum_attempts": result.diagnostics.retry_policy_maximum_attempts,
            "timeout_policy_scope": result.diagnostics.timeout_policy_scope,
            "timeout_policy_seconds": result.diagnostics.timeout_policy_seconds,
        },
        "has_usage": result.usage is not None,
        "limitations": sorted(result.limitations),
        "provider_id": str(result.provider_id),
        "provider_result": (
            diagnostic_view_of_result(result.provider_result)
            if result.provider_result is not None
            else None
        ),
        "retry_count": result.retry_count,
        "status": str(result.status),
        "terminal_error_category": (
            str(result.terminal_error_category)
            if result.terminal_error_category is not None
            else None
        ),
        "timeout_applied": result.timeout_applied,
    }


__all__ = ["diagnostic_view_of_execution_result"]
