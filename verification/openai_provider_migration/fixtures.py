"""Synthetic, in-memory fixtures. No network, no credentials, no waiting.

Every "OpenAI response" and "OpenAI SDK exception" in this suite is built
here from plain Python objects. The adapter classifies SDK failures by
exception *class name*, so :func:`sdk_exception` can exercise the real
classification path without the optional ``openai`` extra being installed and
without any HTTP traffic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
)
from codestrata.ai.prompts import ModernizationPromptBuilder
from codestrata.ai.prompts.models import PromptMessage, PromptMetadata, PromptRequest
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)
from codestrata.ai.providers.models import ModelInvocationOptions, ModernizationModelRequest
from verification.openai_provider_migration.contract import OPENAI_DEFAULT_ANSWER_MODEL

SYNTHETIC_INSTRUCTION = "Synthetic instruction text."
SYNTHETIC_DEVELOPER = "Synthetic developer text."
SYNTHETIC_CONTEXT = '{"synthetic": true}'
SYNTHETIC_RESPONSE_TEXT = '{"synthetic_response": true}'
SYNTHETIC_REQUEST_ID = "synthetic-request-id"


@dataclass
class Usage:
    prompt_tokens: Any = 11
    completion_tokens: Any = 22
    total_tokens: Any = 33


@dataclass
class Message:
    content: Any = SYNTHETIC_RESPONSE_TEXT


@dataclass
class Choice:
    message: Message = field(default_factory=Message)
    finish_reason: Any = "stop"


@dataclass
class Response:
    choices: list[Choice] = field(default_factory=lambda: [Choice()])
    usage: Any = field(default_factory=Usage)
    id: Any = SYNTHETIC_REQUEST_ID


class _Completions:
    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class Client:
    """The only surface the adapter touches: ``chat.completions.create``."""

    def __init__(self, outcome: Any | None = None) -> None:
        self._completions = _Completions(Response() if outcome is None else outcome)
        self.chat = type("_Chat", (), {"completions": self._completions})()

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._completions.calls


def response(text: Any = SYNTHETIC_RESPONSE_TEXT, **overrides: Any) -> Response:
    built = Response(choices=[Choice(message=Message(text))])
    for name, value in overrides.items():
        setattr(built, name, value)
    return built


def sdk_exception(class_name: str, message: str = "synthetic failure") -> Exception:
    """Build an exception whose class name matches an OpenAI SDK exception."""

    return type(class_name, (Exception,), {})(message)


def advisor_payload(
    instruction_text: str = SYNTHETIC_INSTRUCTION,
    context_payload_text: str = SYNTHETIC_CONTEXT,
) -> ModernizationAdvisorInput:
    return ModernizationAdvisorInput(
        instruction_text=instruction_text,
        context_payload_text=context_payload_text,
    )


def provider_request(
    *,
    capability: CapabilityId = CapabilityId.MODERNIZATION_ADVISOR,
    payload: Any | None = None,
    response_expectation: ResponseExpectation = ResponseExpectation.STRUCTURED_JSON,
    model_id: str = OPENAI_DEFAULT_ANSWER_MODEL,
    temperature: float | None = 0.0,
    max_tokens: int | None = 2048,
) -> AIProviderRequest:
    return AIProviderRequest(
        capability=capability,
        payload=payload if payload is not None else advisor_payload(),
        response_expectation=response_expectation,
        model_reference=ProviderModelReference(value=model_id),
        execution_options=ExecutionOptions(temperature=temperature, max_tokens=max_tokens),
    )


def prompt_request(
    *,
    system: str | None = SYNTHETIC_INSTRUCTION,
    developer: str | None = SYNTHETIC_DEVELOPER,
    user: str | None = SYNTHETIC_CONTEXT,
) -> PromptRequest:
    messages: list[PromptMessage] = []
    if system is not None:
        messages.append(PromptMessage(role="system", content=system))
    if developer is not None:
        messages.append(PromptMessage(role="developer", content=developer))
    if user is not None:
        messages.append(PromptMessage(role="user", content=user))
    return PromptRequest(
        messages=messages,
        context_json=SYNTHETIC_CONTEXT,
        expected_output_schema_json='{"type": "object"}',
        metadata=PromptMetadata(
            repository_identifier="synthetic-repository",
            context_schema_version="1.0",
            recommendation_schema_version="1.0",
            finding_count=0,
            technology_count=0,
            context_truncated=False,
            prompt_template_version="1.0",
        ),
    )


def analysis_context() -> LLMAnalysisContext:
    """A minimal, synthetic analysis context for the legacy invoke path."""

    truncation = LLMSectionTruncation(truncated=False, original_count=1, included_count=1)
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="synthetic-repository", source_type="github", file_count=1
        ),
        metrics=LLMMetricsContext(finding_count=1, technology_count=0),
        findings=[
            LLMFindingEvidence(
                rule_id="SYN001",
                title="Synthetic finding",
                category="security",
                severity="high",
                summary="Synthetic summary.",
                evidence_truncation=LLMSectionTruncation(
                    truncated=False, original_count=0, included_count=0
                ),
            )
        ],
        findings_truncation=truncation,
    )


def model_request() -> ModernizationModelRequest:
    """Build the legacy ``invoke()`` request from a synthetic analysis context."""

    context = analysis_context()
    return ModernizationModelRequest(
        prompt_request=ModernizationPromptBuilder().build(context),
        analysis_context=context,
    )


def invocation_options(
    *, model_id: str = OPENAI_DEFAULT_ANSWER_MODEL, request_id: str | None = None
) -> ModelInvocationOptions:
    return ModelInvocationOptions(model_id=model_id, request_id=request_id)


def no_environment(_name: str) -> str | None:
    """An environment reader that reports every variable as unset."""

    return None


__all__ = [
    "SYNTHETIC_CONTEXT",
    "SYNTHETIC_DEVELOPER",
    "SYNTHETIC_INSTRUCTION",
    "SYNTHETIC_REQUEST_ID",
    "SYNTHETIC_RESPONSE_TEXT",
    "Choice",
    "Client",
    "Message",
    "Response",
    "Usage",
    "advisor_payload",
    "analysis_context",
    "invocation_options",
    "model_request",
    "no_environment",
    "prompt_request",
    "provider_request",
    "response",
    "sdk_exception",
]
