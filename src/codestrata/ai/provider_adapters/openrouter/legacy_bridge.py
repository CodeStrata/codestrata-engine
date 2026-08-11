"""Translate between the legacy ``AIModelProvider`` contract and OpenRouter contracts."""

from __future__ import annotations

from codestrata.ai.prompts.models import PromptRequest
from codestrata.ai.provider_adapters.openrouter import error_mapping
from codestrata.ai.provider_adapters.openrouter.configuration import DEFAULT_API_KEY_ENV_NAME
from codestrata.ai.provider_adapters.openrouter.request_mapping import STRUCTURED_JSON_INSTRUCTION
from codestrata.ai.provider_adapters.openrouter.response_mapping import OpenRouterInvocationDetail
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import AIProviderError as ContractProviderError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
)
from codestrata.ai.providers.models import (
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelUsage,
)

OPENROUTER_PROVIDER_NAME = "openrouter"

DEVELOPER_PREFIX = "Developer instructions:\n"
PARAGRAPH_SEPARATOR = "\n\n"
INSTRUCTION_TEXT_FALLBACK = STRUCTURED_JSON_INSTRUCTION


def fold_prompt_request(prompt_request: PromptRequest) -> ModernizationAdvisorInput:
    instruction_parts: list[str] = []
    context_parts: list[str] = []
    for message in prompt_request.messages:
        if message.role == "system":
            instruction_parts.append(message.content)
        elif message.role == "developer":
            instruction_parts.append(f"{DEVELOPER_PREFIX}{message.content}")
        elif message.role == "user":
            context_parts.append(message.content)
        else:  # pragma: no cover
            raise AIProviderConfigurationError(f"Unsupported prompt role: {message.role}")
    if not context_parts:
        raise AIProviderConfigurationError(
            "PromptRequest must include at least one user message with analysis context"
        )
    instruction_text = PARAGRAPH_SEPARATOR.join(
        part for part in instruction_parts if part.strip()
    )
    return ModernizationAdvisorInput(
        instruction_text=instruction_text or INSTRUCTION_TEXT_FALLBACK,
        context_payload_text=PARAGRAPH_SEPARATOR.join(
            part for part in context_parts if part.strip()
        ),
    )


def build_execution_options(options: ModelInvocationOptions) -> ExecutionOptions:
    return ExecutionOptions(
        timeout_seconds=options.timeout_seconds,
        temperature=options.temperature,
        max_tokens=options.max_output_tokens,
    )


def build_provider_request(
    prompt_request: PromptRequest,
    options: ModelInvocationOptions,
    *,
    model_id: str,
    response_expectation: ResponseExpectation = ResponseExpectation.STRUCTURED_JSON,
) -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=fold_prompt_request(prompt_request),
        response_expectation=response_expectation,
        model_reference=ProviderModelReference(value=model_id),
        execution_options=build_execution_options(options),
    )


def build_model_invocation_metadata(
    *,
    model_id: str,
    detail: OpenRouterInvocationDetail,
    request_id_override: str | None = None,
) -> ModelInvocationMetadata:
    return ModelInvocationMetadata(
        provider=OPENROUTER_PROVIDER_NAME,
        model_id=model_id,
        request_id=request_id_override,
        latency_ms=detail.latency_ms,
        usage=ModelUsage(
            input_tokens=detail.input_tokens,
            output_tokens=detail.output_tokens,
            total_tokens=detail.total_tokens,
        ),
        stop_reason=detail.stop_reason,
    )


def _with_detail(template: str, detail: str) -> str:
    return template.format(detail=detail)


_LEGACY_MESSAGES: dict[str, str] = {
    error_mapping.CODE_MISSING_DEPENDENCY: (
        "OpenRouter provider requires the optional 'openai' extra "
        "(OpenAI-compatible client). Install with: pip install 'codestrata[openai]'"
    ),
    error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED: (
        "Failed to configure OpenRouter client: {detail}"
    ),
    error_mapping.CODE_AUTHENTICATION_FAILED: (
        "OpenRouter authentication failed. Verify API key and model access. Details: {detail}"
    ),
    error_mapping.CODE_AUTHORIZATION_FAILED: (
        "OpenRouter authentication failed. Verify API key and model access. Details: {detail}"
    ),
    error_mapping.CODE_TIMEOUT: "OpenRouter temporary service failure: {detail}",
    error_mapping.CODE_RATE_LIMITED: "OpenRouter temporary service failure: {detail}",
    error_mapping.CODE_PROVIDER_UNAVAILABLE: "OpenRouter temporary service failure: {detail}",
    error_mapping.CODE_INVALID_MODEL: (
        "OpenRouter invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_INVALID_REQUEST: (
        "OpenRouter invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_EMPTY_RESPONSE: "OpenRouter response did not include assistant text",
    error_mapping.CODE_UNREADABLE_RESPONSE: "Failed to read OpenRouter chat response: {detail}",
    error_mapping.CODE_PROMPT_MAPPING_FAILED: (
        "OpenRouter invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE: "OpenRouter invocation failed: {detail}",
}

_TIMEOUT_CODES: frozenset[str] = frozenset(
    {
        error_mapping.CODE_TIMEOUT,
        error_mapping.CODE_RATE_LIMITED,
        error_mapping.CODE_PROVIDER_UNAVAILABLE,
    }
)

_CONFIGURATION_CODES: frozenset[str] = frozenset(
    {
        error_mapping.CODE_MISSING_DEPENDENCY,
        error_mapping.CODE_MISSING_API_KEY,
        error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED,
        error_mapping.CODE_AUTHENTICATION_DEFERRED,
    }
)


def legacy_error_for(
    error: ContractProviderError,
    *,
    api_key_env_name: str = DEFAULT_API_KEY_ENV_NAME,
    legacy_detail: str = "",
) -> AIProviderError:
    code = error.code
    if code == error_mapping.CODE_MISSING_API_KEY:
        return AIProviderConfigurationError(
            f"OpenRouter API key not found in environment variable {api_key_env_name}"
        )
    template = _LEGACY_MESSAGES.get(
        code, _LEGACY_MESSAGES[error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE]
    )
    message = _with_detail(template, legacy_detail) if "{detail}" in template else template
    if code in _CONFIGURATION_CODES:
        return AIProviderConfigurationError(message)
    if code in _TIMEOUT_CODES:
        return AIProviderTimeoutError(message)
    return AIProviderInvocationError(message)


__all__ = [
    "DEFAULT_API_KEY_ENV_NAME",
    "DEVELOPER_PREFIX",
    "INSTRUCTION_TEXT_FALLBACK",
    "OPENROUTER_PROVIDER_NAME",
    "PARAGRAPH_SEPARATOR",
    "build_execution_options",
    "build_model_invocation_metadata",
    "build_provider_request",
    "fold_prompt_request",
    "legacy_error_for",
]
