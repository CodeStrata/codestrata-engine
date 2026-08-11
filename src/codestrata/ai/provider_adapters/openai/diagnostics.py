"""Redacted diagnostic views of the OpenAI adapter and one invocation.

Everything here is safe to log, print from a CLI, or embed in a verification
report. None of these views ever contains:

* an API key, or the value of any environment variable;
* the configured base URL (only whether one is configured);
* a model reference value (only ``ProviderModelReference.redacted()``);
* prompt or response text, or a decoded structured payload;
* a provider request ID, a stop reason, or raw/sanitized exception text;
* a filesystem path or a timestamp.

The bridge-only ``OpenAIInvocationDetail`` is deliberately *not* accepted by
any function here — it carries a request ID and sanitized exception text,
which exist solely to rebuild the legacy result contract.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.provider_adapters.openai.adapter import ADAPTER_LIMITATIONS, OpenAIProvider
from codestrata.ai.provider_adapters.openai.capabilities import openai_capability_profile
from codestrata.ai.provider_contracts.capability_diagnostics import (
    diagnostic_view_of_capability_profile,
)
from codestrata.ai.provider_contracts.diagnostics import diagnostic_view_of_result
from codestrata.ai.provider_contracts.execution_diagnostics import (
    diagnostic_view_of_execution_result,
)
from codestrata.ai.provider_contracts.execution_models import AIProviderExecutionResult
from codestrata.ai.provider_contracts.responses import AIProviderResult


def diagnostic_view_of_adapter(adapter: OpenAIProvider) -> dict[str, Any]:
    """Return a safe summary of how an adapter instance is configured."""

    configuration = adapter.configuration
    redacted = configuration.adapter_configuration.redacted()
    return {
        "adapter_limitations": sorted(ADAPTER_LIMITATIONS),
        "api_key_env_name": redacted["api_key_env_name"],
        "base_url_configured": redacted["base_url_configured"],
        "client_injected": adapter.client_injected,
        "max_retries_declared": redacted["max_retries_declared"],
        "provider_id": str(adapter.provider_id),
        "supported_capability_ids": sorted(
            str(capability) for capability in openai_capability_profile().supported_capability_ids
        ),
        "timeout_seconds": configuration.client_inputs.timeout_seconds,
    }


def diagnostic_view_of_capabilities() -> dict[str, Any]:
    """Return the safe capability-profile view the adapter answers ``supports()`` from."""

    return diagnostic_view_of_capability_profile(openai_capability_profile())


def diagnostic_view_of_provider_result(result: AIProviderResult) -> dict[str, Any]:
    """Return the safe, response-free Slice 11.2 view of one adapter result."""

    return diagnostic_view_of_result(result)


def diagnostic_view_of_execution(execution: AIProviderExecutionResult) -> dict[str, Any]:
    """Return the safe, response-free Slice 11.4 view of one executor run."""

    return diagnostic_view_of_execution_result(execution)


def error_category_matrix() -> dict[str, str]:
    """Return the stable diagnostic-code -> error-category mapping this adapter uses."""

    return {
        code: str(category)
        for code, category in sorted(error_mapping.CATEGORY_BY_CODE.items())
    }


def retryability_matrix() -> dict[str, bool]:
    """Return which error category this adapter's codes map to is retryable by default."""

    return {
        code: error_mapping.is_retryable(category)
        for code, category in sorted(error_mapping.CATEGORY_BY_CODE.items())
    }


__all__ = [
    "diagnostic_view_of_adapter",
    "diagnostic_view_of_capabilities",
    "diagnostic_view_of_execution",
    "diagnostic_view_of_provider_result",
    "error_category_matrix",
    "retryability_matrix",
]
