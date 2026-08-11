"""Translate between the legacy ``AIModelProvider`` contract and the new one.

Two directions:

**Inbound** — :func:`fold_prompt_request` collapses a ``PromptRequest``'s
ordered messages into the provider-neutral
:class:`ModernizationAdvisorInput` (``instruction_text`` = system +
``"Developer instructions:\\n"``-prefixed developer text;
``context_payload_text`` = user text). The JSON-mode instruction is
deliberately *not* folded in here — it belongs to the OpenAI wire format and
is appended by ``request_mapping``. :func:`build_provider_request` then wraps
that payload with the model reference and the execution options taken from
``ModelInvocationOptions``.

**Outbound** — :func:`legacy_error_for` rebuilds the exact legacy exception
type *and message* the pre-migration provider raised, keyed off the bounded
``AIProviderError.code`` plus the sanitized ``legacy_error_detail`` carried on
the bridge-only invocation detail. This is what keeps
``AiEnrichmentService``'s fail-soft behavior byte-identical: the enrichment
path catches ``AIProviderError`` subclasses, and which subclass it sees (and
what message it records) is unchanged by the migration.
:func:`build_model_invocation_metadata` likewise rebuilds
``ModelInvocationMetadata`` — including the provider-reported token triple
verbatim, so an inconsistent triple is reported exactly as before.
"""

from __future__ import annotations

from codestrata.ai.prompts.models import PromptRequest
from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.provider_adapters.openai.configuration import DEFAULT_API_KEY_ENV_NAME
from codestrata.ai.provider_adapters.openai.request_mapping import STRUCTURED_JSON_INSTRUCTION
from codestrata.ai.provider_adapters.openai.response_mapping import OpenAIInvocationDetail
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

OPENAI_PROVIDER_NAME = "openai"

DEVELOPER_PREFIX = "Developer instructions:\n"
PARAGRAPH_SEPARATOR = "\n\n"

# Fallback instruction text for the degenerate case of a prompt with no
# system/developer messages. ModernizationAdvisorInput requires a non-empty
# instruction_text, and the pre-migration provider produced a system message
# containing only the JSON instruction in that case; request_mapping's
# no-double-append rule makes the two byte-identical.
INSTRUCTION_TEXT_FALLBACK = STRUCTURED_JSON_INSTRUCTION


def fold_prompt_request(prompt_request: PromptRequest) -> ModernizationAdvisorInput:
    """Fold an ordered ``PromptRequest`` into the provider-neutral capability payload.

    Raises ``AIProviderConfigurationError`` for an unsupported role or a
    prompt with no user message — the same two configuration errors, with the
    same messages, the pre-migration provider raised.
    """

    instruction_parts: list[str] = []
    context_parts: list[str] = []
    for message in prompt_request.messages:
        if message.role == "system":
            instruction_parts.append(message.content)
        elif message.role == "developer":
            instruction_parts.append(f"{DEVELOPER_PREFIX}{message.content}")
        elif message.role == "user":
            context_parts.append(message.content)
        else:  # pragma: no cover - PromptRole is a closed Literal
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
    """Carry the legacy invocation options across as contract execution options."""

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
    """Build the contract request for one Modernization Advisor invocation."""

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
    detail: OpenAIInvocationDetail,
    request_id_override: str | None = None,
) -> ModelInvocationMetadata:
    """Rebuild the legacy invocation metadata from the bridge-only detail."""

    return ModelInvocationMetadata(
        provider=OPENAI_PROVIDER_NAME,
        model_id=model_id,
        request_id=request_id_override or detail.request_id,
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


# Legacy message templates, reproduced verbatim from the pre-migration
# provider so nothing downstream of the enrichment fail-soft path observes a
# different message. Keyed by the bounded diagnostic code because several
# codes share one ErrorCategory but raised different legacy messages.
_LEGACY_MESSAGES: dict[str, str] = {
    error_mapping.CODE_MISSING_DEPENDENCY: (
        "OpenAI provider requires the optional 'openai' extra. "
        "Install with: pip install 'codestrata[openai]'"
    ),
    error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED: "Failed to configure OpenAI client: {detail}",
    error_mapping.CODE_AUTHENTICATION_FAILED: (
        "OpenAI authentication failed. Verify API key and model access. Details: {detail}"
    ),
    error_mapping.CODE_AUTHORIZATION_FAILED: (
        "OpenAI authentication failed. Verify API key and model access. Details: {detail}"
    ),
    error_mapping.CODE_TIMEOUT: "OpenAI temporary service failure: {detail}",
    error_mapping.CODE_RATE_LIMITED: "OpenAI temporary service failure: {detail}",
    error_mapping.CODE_PROVIDER_UNAVAILABLE: "OpenAI temporary service failure: {detail}",
    error_mapping.CODE_INVALID_MODEL: "OpenAI invalid model or request configuration: {detail}",
    error_mapping.CODE_INVALID_REQUEST: "OpenAI invalid model or request configuration: {detail}",
    error_mapping.CODE_EMPTY_RESPONSE: "OpenAI response did not include assistant text",
    error_mapping.CODE_UNREADABLE_RESPONSE: "Failed to read OpenAI chat response: {detail}",
    error_mapping.CODE_PROMPT_MAPPING_FAILED: (
        "OpenAI invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE: "OpenAI invocation failed: {detail}",
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
    }
)


def legacy_error_for(
    error: ContractProviderError,
    *,
    api_key_env_name: str = DEFAULT_API_KEY_ENV_NAME,
    legacy_detail: str = "",
) -> AIProviderError:
    """Map a bounded contract error back onto the legacy exception to raise.

    ``api_key_env_name`` is only used to rebuild the missing-key message,
    which names the environment variable (never its value) exactly as the
    pre-migration provider did.
    """

    code = error.code
    if code == error_mapping.CODE_MISSING_API_KEY:
        return AIProviderConfigurationError(
            f"OpenAI API key not found in environment variable {api_key_env_name}"
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
    "OPENAI_PROVIDER_NAME",
    "PARAGRAPH_SEPARATOR",
    "build_execution_options",
    "build_model_invocation_metadata",
    "build_provider_request",
    "fold_prompt_request",
    "legacy_error_for",
]
