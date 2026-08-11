"""Translate between the legacy ``AIModelProvider`` contract and the new one.

Two directions:

**Inbound** — :func:`fold_prompt_request` collapses a ``PromptRequest``'s
ordered messages into the provider-neutral
:class:`ModernizationAdvisorInput` (``instruction_text`` = system +
``"Developer instructions:\\n"``-prefixed developer text;
``context_payload_text`` = user text). The JSON-mode instruction is
deliberately *not* folded in here — it belongs to the Converse wire format
and is appended by ``request_mapping``. :func:`build_provider_request` then
wraps that payload with the model reference and the execution options taken
from ``ModelInvocationOptions``.

**Outbound** — :func:`legacy_error_for` rebuilds the exact legacy exception
type *and message* the pre-migration provider raised, keyed off the bounded
``AIProviderError.code`` plus the sanitized ``legacy_error_detail`` (and, for
the generic service-error message, the ``legacy_error_label``) carried on the
bridge-only invocation detail. This is what keeps ``AiEnrichmentService``'s
fail-soft behavior byte-identical: the enrichment path catches
``AIProviderError`` subclasses, and which subclass it sees (and what message
it records) is unchanged by the migration.
:func:`build_model_invocation_metadata` likewise rebuilds
``ModelInvocationMetadata`` — including the reported token triple verbatim,
so an inconsistent triple is reported exactly as before.

This module may import ``codestrata.ai.aws_config``, but only for
:func:`format_aws_authentication_error`, which is a pure string formatter: it
reads no environment variable, imports no SDK, and contacts no AWS service.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.ai.aws_config import format_aws_authentication_error
from codestrata.ai.prompts.models import PromptMessage, PromptRequest
from codestrata.ai.provider_adapters.bedrock import error_mapping
from codestrata.ai.provider_adapters.bedrock.request_mapping import STRUCTURED_JSON_INSTRUCTION
from codestrata.ai.provider_adapters.bedrock.response_mapping import BedrockInvocationDetail
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

BEDROCK_PROVIDER_NAME = "bedrock"

DEVELOPER_PREFIX = "Developer instructions:\n"
PARAGRAPH_SEPARATOR = "\n\n"

# Fallback instruction text for the degenerate case of a prompt with no
# system/developer messages. ModernizationAdvisorInput requires a non-empty
# instruction_text, and the pre-migration provider produced a system block
# containing only the JSON instruction in that case; request_mapping's
# no-double-append rule makes the two byte-identical.
INSTRUCTION_TEXT_FALLBACK = STRUCTURED_JSON_INSTRUCTION


def fold_prompt_messages(messages: Sequence[PromptMessage]) -> ModernizationAdvisorInput:
    """Fold ordered prompt messages into the provider-neutral capability payload.

    Raises ``AIProviderConfigurationError`` for an unsupported role, a prompt
    with no user message, or an all-blank user message — the same three
    configuration errors, with the same messages, the pre-migration
    ``split_prompt_for_converse`` raised.
    """

    instruction_parts: list[str] = []
    context_parts: list[str] = []
    for message in messages:
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
    context_payload_text = PARAGRAPH_SEPARATOR.join(
        part for part in context_parts if part.strip()
    )
    if not context_payload_text.strip():
        raise AIProviderConfigurationError("PromptRequest user message must be nonempty")
    instruction_text = PARAGRAPH_SEPARATOR.join(
        part for part in instruction_parts if part.strip()
    )
    return ModernizationAdvisorInput(
        instruction_text=instruction_text or INSTRUCTION_TEXT_FALLBACK,
        context_payload_text=context_payload_text,
    )


def fold_prompt_request(prompt_request: PromptRequest) -> ModernizationAdvisorInput:
    """Fold an ordered ``PromptRequest`` into the provider-neutral capability payload."""

    return fold_prompt_messages(prompt_request.messages)


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
    detail: BedrockInvocationDetail,
    request_id_override: str | None = None,
) -> ModelInvocationMetadata:
    """Rebuild the legacy invocation metadata from the bridge-only detail."""

    return ModelInvocationMetadata(
        provider=BEDROCK_PROVIDER_NAME,
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


# Legacy message templates, reproduced verbatim from the pre-migration
# provider so nothing downstream of the enrichment fail-soft path observes a
# different message. Keyed by the bounded diagnostic code because several
# codes share one ErrorCategory but raised different legacy messages.
#
# ``{detail}`` interpolates the sanitized exception text; ``{label}``
# interpolates the AWS error code (or exception class name) the legacy
# "service error" message named.
_LEGACY_MESSAGES: dict[str, str] = {
    error_mapping.CODE_MISSING_DEPENDENCY: "{detail}",
    error_mapping.CODE_CLIENT_AUTHENTICATION_FAILED: "{detail}",
    error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED: "{detail}",
    error_mapping.CODE_AWS_AUTHENTICATION_ERROR: "{detail}",
    error_mapping.CODE_AUTHORIZATION_FAILED: (
        "Bedrock model access denied. Verify IAM permissions for Bedrock "
        "and the selected model. Details: {detail}"
    ),
    error_mapping.CODE_TIMEOUT: "Bedrock invocation timed out: {detail}",
    error_mapping.CODE_MODEL_TIMEOUT: "Bedrock temporary service failure: {detail}",
    error_mapping.CODE_RATE_LIMITED: "Bedrock temporary service failure: {detail}",
    error_mapping.CODE_PROVIDER_UNAVAILABLE: "Bedrock temporary service failure: {detail}",
    error_mapping.CODE_INVALID_MODEL: (
        "Bedrock invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_INVALID_REQUEST: (
        "Bedrock invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_SERVICE_ERROR: "Bedrock service error ({label}): {detail}",
    error_mapping.CODE_RESPONSE_NOT_A_MAPPING: "Bedrock Converse response must be a mapping",
    error_mapping.CODE_RESPONSE_MISSING_OUTPUT: (
        "Bedrock Converse response is missing output"
    ),
    error_mapping.CODE_RESPONSE_MISSING_MESSAGE: (
        "Bedrock Converse response is missing output.message"
    ),
    error_mapping.CODE_RESPONSE_MISSING_CONTENT: (
        "Bedrock Converse response is missing output.message.content"
    ),
    error_mapping.CODE_EMPTY_RESPONSE: (
        "Bedrock Converse response did not include assistant text content"
    ),
    error_mapping.CODE_UNREADABLE_RESPONSE: (
        "Failed to read Bedrock Converse response: {detail}"
    ),
    error_mapping.CODE_PARSING_FAILED: (
        "Unexpected failure while parsing Bedrock response: {detail}"
    ),
    error_mapping.CODE_PROMPT_MAPPING_FAILED: (
        "Bedrock invalid model or request configuration: {detail}"
    ),
    error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE: "Bedrock invocation failed: {detail}",
}

# ``AIProviderTimeoutError`` covered both real timeouts and AWS "temporary
# service failure" conditions in the pre-migration provider; that grouping is
# preserved so the enrichment fail-soft path sees the same exception type.
_TIMEOUT_CODES: frozenset[str] = frozenset(
    {
        error_mapping.CODE_TIMEOUT,
        error_mapping.CODE_MODEL_TIMEOUT,
        error_mapping.CODE_RATE_LIMITED,
        error_mapping.CODE_PROVIDER_UNAVAILABLE,
    }
)

# Failures that happened while *building* the client. Pre-migration these
# were raised from ``__init__`` as ``AIProviderConfigurationError``; with lazy
# construction they are raised from ``invoke()`` instead, as the same type
# with the same message.
_CONFIGURATION_CODES: frozenset[str] = frozenset(
    {
        error_mapping.CODE_MISSING_DEPENDENCY,
        error_mapping.CODE_CLIENT_AUTHENTICATION_FAILED,
        error_mapping.CODE_CLIENT_CONSTRUCTION_FAILED,
    }
)


def _render(template: str, *, detail: str, label: str) -> str:
    if "{detail}" not in template and "{label}" not in template:
        return template
    return template.format(detail=detail, label=label)


def legacy_error_for(
    error: ContractProviderError,
    *,
    profile_name: str | None = None,
    legacy_detail: str = "",
    legacy_label: str = "",
) -> AIProviderError:
    """Map a bounded contract error back onto the legacy exception to raise.

    ``profile_name`` is only used to rebuild the AWS authentication guidance,
    which names the profile (never a credential) exactly as the pre-migration
    provider did through ``format_aws_authentication_error``.
    """

    code = error.code
    if code == error_mapping.CODE_AUTHENTICATION_FAILED:
        return AIProviderInvocationError(format_aws_authentication_error(profile=profile_name))
    template = _LEGACY_MESSAGES.get(
        code, _LEGACY_MESSAGES[error_mapping.CODE_UNEXPECTED_INVOCATION_FAILURE]
    )
    message = _render(template, detail=legacy_detail, label=legacy_label)
    if code in _CONFIGURATION_CODES:
        return AIProviderConfigurationError(message)
    if code in _TIMEOUT_CODES:
        return AIProviderTimeoutError(message)
    return AIProviderInvocationError(message)


__all__ = [
    "BEDROCK_PROVIDER_NAME",
    "DEVELOPER_PREFIX",
    "INSTRUCTION_TEXT_FALLBACK",
    "PARAGRAPH_SEPARATOR",
    "build_execution_options",
    "build_model_invocation_metadata",
    "build_provider_request",
    "fold_prompt_messages",
    "fold_prompt_request",
    "format_aws_authentication_error",
    "legacy_error_for",
]
