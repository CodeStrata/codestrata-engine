"""Map an ``AIProviderRequest`` onto OpenAI Chat Completions call kwargs.

The produced kwargs are byte-identical to what the pre-migration
``openai_provider._chat_messages`` + ``client.chat.completions.create(...)``
call site produced:

* exactly two messages: one ``system`` message then one ``user`` message;
* the system message is the folded instruction text, and — for a
  ``STRUCTURED_JSON`` request — :data:`STRUCTURED_JSON_INSTRUCTION` appended
  as a final ``"\\n\\n"``-separated paragraph;
* the user message is the folded context payload text;
* ``model``, ``temperature``, ``max_tokens`` and, for ``STRUCTURED_JSON``,
  ``response_format={"type": "json_object"}``.

A ``TEXT`` request omits both the JSON instruction paragraph and
``response_format`` — that path exists for contract completeness and is not
reached by ``codestrata assess``, which always asks for structured JSON.

The mapping is pure and fingerprintable: same request in, same kwargs out,
with no environment reads, no clock, and no client.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation

STRUCTURED_JSON_INSTRUCTION = (
    "Respond with a single JSON object only. Do not include markdown fences or prose."
)

JSON_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}

PARAGRAPH_SEPARATOR = "\n\n"

SYSTEM_ROLE = "system"
USER_ROLE = "user"


def build_system_content(
    instruction_text: str,
    *,
    response_expectation: ResponseExpectation,
) -> str:
    """Compose the system message content for ``instruction_text``.

    Appends :data:`STRUCTURED_JSON_INSTRUCTION` for a structured-JSON
    expectation, but never twice: a folded instruction text that already ends
    with that exact sentence is left alone. This keeps the degenerate case (a
    prompt with no system/developer messages, where the folded instruction
    text *is* the JSON instruction) byte-identical to the pre-migration
    behavior.
    """

    parts = [instruction_text] if instruction_text.strip() else []
    wants_json = response_expectation is ResponseExpectation.STRUCTURED_JSON
    if wants_json and not instruction_text.endswith(STRUCTURED_JSON_INSTRUCTION):
        parts.append(STRUCTURED_JSON_INSTRUCTION)
    return PARAGRAPH_SEPARATOR.join(parts)


def build_chat_messages(
    payload: ModernizationAdvisorInput,
    *,
    response_expectation: ResponseExpectation,
) -> list[dict[str, str]]:
    """Build the ordered ``[system, user]`` Chat Completions message array."""

    messages: list[dict[str, str]] = []
    system_content = build_system_content(
        payload.instruction_text, response_expectation=response_expectation
    )
    if system_content:
        messages.append({"role": SYSTEM_ROLE, "content": system_content})
    messages.append({"role": USER_ROLE, "content": payload.context_payload_text})
    return messages


def build_chat_completion_kwargs(request: AIProviderRequest) -> dict[str, Any]:
    """Map ``request`` onto the exact kwargs passed to ``chat.completions.create``."""

    if not isinstance(request, AIProviderRequest):
        raise ProviderContractValidationError("request must be an AIProviderRequest")
    payload = request.payload
    if not isinstance(payload, ModernizationAdvisorInput):
        raise ProviderContractValidationError(
            "OpenAI adapter requires a ModernizationAdvisorInput payload"
        )
    model = request.model_reference.value.strip()
    if not model:
        raise ProviderContractValidationError("model_reference must resolve to a non-empty model")

    options = request.execution_options
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": build_chat_messages(
            payload, response_expectation=request.response_expectation
        ),
    }
    if options.temperature is not None:
        kwargs["temperature"] = options.temperature
    if options.max_tokens is not None:
        kwargs["max_tokens"] = options.max_tokens
    if request.response_expectation is ResponseExpectation.STRUCTURED_JSON:
        kwargs["response_format"] = dict(JSON_RESPONSE_FORMAT)
    return kwargs


def request_shape(request: AIProviderRequest) -> dict[str, Any]:
    """Return a prompt-free structural summary of the mapped call.

    Records which kwargs would be sent and the message role order — never the
    message contents, the model value, or any option value.
    """

    kwargs = build_chat_completion_kwargs(request)
    messages = kwargs["messages"]
    return {
        "json_mode_requested": "response_format" in kwargs,
        "kwarg_names": sorted(kwargs),
        "message_count": len(messages),
        "message_roles": [message["role"] for message in messages],
    }


__all__ = [
    "JSON_RESPONSE_FORMAT",
    "PARAGRAPH_SEPARATOR",
    "STRUCTURED_JSON_INSTRUCTION",
    "SYSTEM_ROLE",
    "USER_ROLE",
    "build_chat_completion_kwargs",
    "build_chat_messages",
    "build_system_content",
    "request_shape",
]
