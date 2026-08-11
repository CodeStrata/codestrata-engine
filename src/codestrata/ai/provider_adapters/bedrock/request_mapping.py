"""Map an ``AIProviderRequest`` onto AWS Bedrock Converse call kwargs.

The produced kwargs are byte-identical to what the pre-migration
``bedrock.build_converse_request`` + ``client.converse(...)`` call site
produced:

* ``modelId`` — the stripped model reference;
* ``messages`` — exactly one ``user`` message with a single ``{"text": ...}``
  content block holding the folded context payload;
* ``inferenceConfig`` — ``{"maxTokens": ..., "temperature": ...}``;
* ``system`` — present only when the folded instruction text is non-empty, as
  a single ``[{"text": ...}]`` block.

Bedrock Converse has **no** OpenAI-style ``response_format``. Structured JSON
is requested by appending :data:`STRUCTURED_JSON_INSTRUCTION` to the system
block as a final ``"\\n\\n"``-separated paragraph — the prompt-instruction-only
strategy the capability profile records with ``supports_structured_json=False``.
The pre-migration provider appended that sentence unconditionally; the
``TEXT`` expectation path here omits it and exists for contract completeness
only, since ``codestrata assess`` always asks for structured JSON.

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

PARAGRAPH_SEPARATOR = "\n\n"

USER_ROLE = "user"

MODEL_ID_KEY = "modelId"
MESSAGES_KEY = "messages"
INFERENCE_CONFIG_KEY = "inferenceConfig"
SYSTEM_KEY = "system"
MAX_TOKENS_KEY = "maxTokens"
TEMPERATURE_KEY = "temperature"


def build_system_text(
    instruction_text: str,
    *,
    response_expectation: ResponseExpectation,
) -> str:
    """Compose the Converse ``system`` block text for ``instruction_text``.

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


def build_messages(payload: ModernizationAdvisorInput) -> list[dict[str, Any]]:
    """Build the single-element Converse ``messages`` array."""

    return [
        {
            "role": USER_ROLE,
            "content": [{"text": payload.context_payload_text}],
        }
    ]


def build_converse_kwargs(request: AIProviderRequest) -> dict[str, Any]:
    """Map ``request`` onto the exact kwargs passed to ``client.converse``."""

    if not isinstance(request, AIProviderRequest):
        raise ProviderContractValidationError("request must be an AIProviderRequest")
    payload = request.payload
    if not isinstance(payload, ModernizationAdvisorInput):
        raise ProviderContractValidationError(
            "Bedrock adapter requires a ModernizationAdvisorInput payload"
        )
    model = request.model_reference.value.strip()
    if not model:
        raise ProviderContractValidationError("model_reference must resolve to a non-empty model")

    options = request.execution_options
    inference_config: dict[str, Any] = {}
    if options.max_tokens is not None:
        inference_config[MAX_TOKENS_KEY] = options.max_tokens
    if options.temperature is not None:
        inference_config[TEMPERATURE_KEY] = options.temperature

    kwargs: dict[str, Any] = {
        MODEL_ID_KEY: model,
        MESSAGES_KEY: build_messages(payload),
        INFERENCE_CONFIG_KEY: inference_config,
    }
    system_text = build_system_text(
        payload.instruction_text, response_expectation=request.response_expectation
    )
    if system_text:
        kwargs[SYSTEM_KEY] = [{"text": system_text}]
    return kwargs


def request_shape(request: AIProviderRequest) -> dict[str, Any]:
    """Return a prompt-free structural summary of the mapped call.

    Records which kwargs would be sent and the message role order — never the
    message contents, the model value, or any option value.
    """

    kwargs = build_converse_kwargs(request)
    messages = kwargs[MESSAGES_KEY]
    return {
        "inference_config_keys": sorted(kwargs[INFERENCE_CONFIG_KEY]),
        "json_mode_requested": False,
        "kwarg_names": sorted(kwargs),
        "message_count": len(messages),
        "message_roles": [message["role"] for message in messages],
        "system_block_present": SYSTEM_KEY in kwargs,
    }


__all__ = [
    "INFERENCE_CONFIG_KEY",
    "MAX_TOKENS_KEY",
    "MESSAGES_KEY",
    "MODEL_ID_KEY",
    "PARAGRAPH_SEPARATOR",
    "STRUCTURED_JSON_INSTRUCTION",
    "SYSTEM_KEY",
    "TEMPERATURE_KEY",
    "USER_ROLE",
    "build_converse_kwargs",
    "build_messages",
    "build_system_text",
    "request_shape",
]
