"""Synthetic fixtures for SV.11.9 — no network, no credentials, no waiting."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)
from verification.openrouter_provider.contract import TEST_ONLY_MODEL_REFERENCE


class Usage:
    def __init__(
        self,
        prompt_tokens: int | None = 2,
        completion_tokens: int | None = 3,
        total_tokens: int | None = 5,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class Message:
    def __init__(self, content: str = '{"summary":"synthetic"}') -> None:
        self.content = content


class Choice:
    def __init__(self, content: str = '{"summary":"synthetic"}', finish_reason: str = "stop") -> None:
        self.message = Message(content)
        self.finish_reason = finish_reason


class Response:
    def __init__(
        self,
        content: str = '{"summary":"synthetic"}',
        *,
        usage: Usage | None = None,
        response_id: str = "resp_should_never_appear",
    ) -> None:
        self.choices = [Choice(content)]
        self.usage = usage if usage is not None else Usage()
        self.id = response_id


class Client:
    def __init__(self, response: Any | None = None, error: BaseException | None = None) -> None:
        self._response = response if response is not None else Response()
        self._error = error
        self.calls: list[dict[str, Any]] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if self._error is not None:
            raise self._error
        return self._response


def sdk_exception(class_name: str, message: str = "synthetic") -> Exception:
    return type(class_name, (Exception,), {})(message)


def provider_request(
    *,
    model_id: str = TEST_ONLY_MODEL_REFERENCE,
    structured: bool = True,
) -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text="Synthetic instruction text",
            context_payload_text="Synthetic context payload",
        ),
        response_expectation=(
            ResponseExpectation.STRUCTURED_JSON if structured else ResponseExpectation.TEXT
        ),
        model_reference=ProviderModelReference(model_id),
        execution_options=ExecutionOptions(),
    )


__all__ = [
    "Choice",
    "Client",
    "Message",
    "Response",
    "Usage",
    "provider_request",
    "sdk_exception",
]
