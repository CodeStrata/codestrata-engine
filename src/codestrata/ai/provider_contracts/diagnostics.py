"""Safe, privacy-preserving diagnostic views of requests and results.

These views are what a future logger, CLI diagnostics command, or
verification report is allowed to record. They never include:

* prompt/response text (``instruction_text``, ``context_payload_text``,
  ``AIProviderResultContent.text``/``structured_payload``)
* credentials
* filesystem paths
* raw model reference values (only :meth:`ProviderModelReference.redacted`)
* SDK objects or raw exception text
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult


def diagnostic_view_of_request(request: AIProviderRequest) -> dict[str, Any]:
    """Return a safe, prompt-free summary of a request."""

    options = request.execution_options
    return {
        "capability": str(request.capability),
        "contract_version": request.contract_version,
        "execution_options_present": {
            "max_tokens": options.max_tokens is not None,
            "temperature": options.temperature is not None,
            "timeout_seconds": options.timeout_seconds is not None,
        },
        "model_reference": request.model_reference.redacted(),
        "response_expectation": str(request.response_expectation),
    }


def diagnostic_view_of_result(result: AIProviderResult) -> dict[str, Any]:
    """Return a safe, response-free summary of a result."""

    return {
        "capability": str(result.capability),
        "contract_version": result.contract_version,
        "error_category": str(result.error.category) if result.error is not None else None,
        "error_code": result.error.code if result.error is not None else None,
        "has_content": result.content is not None,
        "has_usage": result.usage is not None,
        "limitations": sorted(result.limitations),
        "provider_id": str(result.provider_id),
        "status": str(result.status),
    }


__all__ = [
    "diagnostic_view_of_request",
    "diagnostic_view_of_result",
]
