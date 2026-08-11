"""Redacted diagnostic views of the OpenRouter adapter."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openrouter import error_mapping
from codestrata.ai.provider_adapters.openrouter.adapter import ADAPTER_LIMITATIONS, OpenRouterProvider
from codestrata.ai.provider_adapters.openrouter.capabilities import openrouter_capability_profile
from codestrata.ai.provider_contracts.capability_diagnostics import (
    diagnostic_view_of_capability_profile,
)
from codestrata.ai.provider_contracts.diagnostics import diagnostic_view_of_result
from codestrata.ai.provider_contracts.execution_diagnostics import (
    diagnostic_view_of_execution_result,
)
from codestrata.ai.provider_contracts.execution_models import AIProviderExecutionResult
from codestrata.ai.provider_contracts.responses import AIProviderResult


def diagnostic_view_of_adapter(adapter: OpenRouterProvider) -> dict[str, Any]:
    configuration = adapter.configuration
    redacted = configuration.adapter_configuration.redacted()
    return {
        "adapter_limitations": sorted(ADAPTER_LIMITATIONS),
        "api_key_env_name": redacted.get("api_key_env_name"),
        "api_key_present": redacted["api_key_present"],
        "app_name_configured": redacted.get("app_name_configured", False),
        "base_url_configured": redacted["base_url_configured"],
        "client_injected": adapter.client_injected,
        "max_retries_declared": redacted["max_retries_declared"],
        "provider_id": str(adapter.provider_id),
        "site_url_configured": redacted.get("site_url_configured", False),
        "supported_capability_ids": sorted(
            str(capability)
            for capability in openrouter_capability_profile().supported_capability_ids
        ),
        "supports_structured_json": openrouter_capability_profile().supports_structured_json,
        "timeout_seconds": configuration.client_inputs.timeout_seconds,
    }


def diagnostic_view_of_capabilities() -> dict[str, Any]:
    return diagnostic_view_of_capability_profile(openrouter_capability_profile())


def diagnostic_view_of_provider_result(result: AIProviderResult) -> dict[str, Any]:
    return diagnostic_view_of_result(result)


def diagnostic_view_of_execution(execution: AIProviderExecutionResult) -> dict[str, Any]:
    return diagnostic_view_of_execution_result(execution)


def error_category_matrix() -> dict[str, str]:
    return {
        code: str(category)
        for code, category in sorted(error_mapping.CATEGORY_BY_CODE.items())
    }


def retryability_matrix() -> dict[str, bool]:
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
