"""In-memory OpenAI SDK doubles. Nothing here touches the network or a credential."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from codestrata.ai.prompts.models import PromptMessage, PromptMetadata, PromptRequest
from codestrata.ai.provider_adapters.openai.configuration import (
    OpenAIRuntimeConfiguration,
    build_runtime_configuration,
)
from codestrata.ai.provider_adapters.openai.response_mapping import OpenAIInvocationDetail
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)

DEFAULT_MODEL_ID = "gpt-4o-mini"


@dataclass
class FakeUsage:
    prompt_tokens: Any = 10
    completion_tokens: Any = 20
    total_tokens: Any = 30


@dataclass
class FakeMessage:
    content: Any = "{}"


@dataclass
class FakeChoice:
    message: FakeMessage = field(default_factory=FakeMessage)
    finish_reason: Any = "stop"


@dataclass
class FakeResponse:
    choices: list[FakeChoice] = field(default_factory=lambda: [FakeChoice()])
    usage: Any = field(default_factory=FakeUsage)
    id: Any = "chatcmpl-fake"


class FakeCompletions:
    """Records the kwargs of each call and replays a scripted outcome."""

    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        if callable(self._outcome):
            return self._outcome(**kwargs)
        return self._outcome


class FakeClient:
    """The minimal ``client.chat.completions.create`` surface the adapter uses."""

    def __init__(self, outcome: Any | None = None) -> None:
        response = FakeResponse() if outcome is None else outcome
        self.completions = FakeCompletions(response)
        self.chat = type("_Chat", (), {"completions": self.completions})()

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.completions.calls


def json_response(payload: dict[str, Any], **kwargs: Any) -> FakeResponse:
    """Build a fake response whose assistant text is ``payload`` as compact JSON."""

    response = FakeResponse(choices=[FakeChoice(message=FakeMessage(json.dumps(payload)))])
    for name, value in kwargs.items():
        setattr(response, name, value)
    return response


def text_response(text: Any, **kwargs: Any) -> FakeResponse:
    """Build a fake response whose assistant text is ``text`` verbatim."""

    response = FakeResponse(choices=[FakeChoice(message=FakeMessage(text))])
    for name, value in kwargs.items():
        setattr(response, name, value)
    return response


def runtime_configuration(**kwargs: Any) -> OpenAIRuntimeConfiguration:
    return build_runtime_configuration(**kwargs)


def advisor_payload(
    instruction_text: str = "Be precise.",
    context_payload_text: str = '{"findings": []}',
) -> ModernizationAdvisorInput:
    return ModernizationAdvisorInput(
        instruction_text=instruction_text,
        context_payload_text=context_payload_text,
    )


def provider_request(
    *,
    payload: Any | None = None,
    capability: CapabilityId = CapabilityId.MODERNIZATION_ADVISOR,
    response_expectation: ResponseExpectation = ResponseExpectation.STRUCTURED_JSON,
    model_id: str = DEFAULT_MODEL_ID,
    temperature: float | None = 0.0,
    max_tokens: int | None = 2048,
    timeout_seconds: float | None = 30.0,
) -> AIProviderRequest:
    return AIProviderRequest(
        capability=capability,
        payload=payload if payload is not None else advisor_payload(),
        response_expectation=response_expectation,
        model_reference=ProviderModelReference(value=model_id),
        execution_options=ExecutionOptions(
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            max_tokens=max_tokens,
        ),
    )


def prompt_metadata() -> PromptMetadata:
    return PromptMetadata(
        repository_identifier="sample-app",
        context_schema_version="1.0",
        recommendation_schema_version="1.0",
        finding_count=0,
        technology_count=0,
        context_truncated=False,
        prompt_template_version="1.0",
    )


def prompt_request(
    *,
    system: str | None = "System rules.",
    developer: str | None = "Developer rules.",
    user: str | None = '{"findings": []}',
    extra_messages: list[PromptMessage] | None = None,
) -> PromptRequest:
    messages: list[PromptMessage] = []
    if system is not None:
        messages.append(PromptMessage(role="system", content=system))
    if developer is not None:
        messages.append(PromptMessage(role="developer", content=developer))
    if user is not None:
        messages.append(PromptMessage(role="user", content=user))
    messages.extend(extra_messages or [])
    return PromptRequest(
        messages=messages,
        context_json='{"findings": []}',
        expected_output_schema_json='{"type": "object"}',
        metadata=prompt_metadata(),
    )


def invocation_detail(**kwargs: Any) -> OpenAIInvocationDetail:
    """Build a bridge-only invocation detail with a default zero latency."""

    kwargs.setdefault("latency_ms", 0.0)
    return OpenAIInvocationDetail(**kwargs)


def named_exception(name: str, message: str = "boom") -> Exception:
    """Build an exception whose class *name* matches an OpenAI SDK exception.

    The adapter classifies SDK failures by class name so it never has to
    import the optional ``openai`` extra; these doubles exercise that path
    without the SDK installed.
    """

    return type(name, (Exception,), {})(message)


__all__ = [
    "DEFAULT_MODEL_ID",
    "FakeChoice",
    "FakeClient",
    "FakeCompletions",
    "FakeMessage",
    "FakeResponse",
    "FakeUsage",
    "advisor_payload",
    "invocation_detail",
    "json_response",
    "named_exception",
    "prompt_metadata",
    "prompt_request",
    "provider_request",
    "runtime_configuration",
    "text_response",
]
