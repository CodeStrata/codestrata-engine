"""Synthetic fixtures for SV.11.11 — no network, no real credentials, no waiting."""

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
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)
from codestrata.ai.providers.models import ModelInvocationOptions, ModernizationModelRequest
from codestrata.config.settings import CodestrataSettings
from verification.openrouter_doctor_integration.contract import (
    DEFAULT_API_KEY_ENV,
    TEST_ONLY_MODEL,
)

SYNTHETIC_INSTRUCTION = "Synthetic instruction text"
SYNTHETIC_CONTEXT = "Synthetic context payload"
# Enrichment-shaped so OpenRouterAIModelProvider.invoke returns without
# recommendation-schema validation (looks_like_enrichment_payload).
SYNTHETIC_RESPONSE = (
    '{"executive_summary":{"overview":"synthetic"},"themes":[],"priorities":[]}'
)
SYNTHETIC_API_KEY = "synthetic-openrouter-key-value"
SYNTHETIC_OPENAI_API_KEY = "synthetic-openai-key-value"
SYNTHETIC_SITE_URL = "https://example.invalid/site"
SYNTHETIC_APP_NAME = "LeakProbeApp"
SYNTHETIC_INVALID_BASE_URL = "http://example.invalid/api/v1"
SYNTHETIC_INVALID_SITE_URL = "http://example.invalid/site"


@dataclass
class Usage:
    prompt_tokens: Any = 2
    completion_tokens: Any = 3
    total_tokens: Any = 5


@dataclass
class Message:
    content: Any = SYNTHETIC_RESPONSE


@dataclass
class Choice:
    message: Message = field(default_factory=Message)
    finish_reason: Any = "stop"


@dataclass
class Response:
    choices: list[Choice] = field(default_factory=lambda: [Choice()])
    usage: Any = field(default_factory=Usage)
    id: Any = "resp_should_never_appear"

    @classmethod
    def empty(cls) -> Response:
        return cls(choices=[Choice(message=Message(content="   "))])

    @classmethod
    def malformed(cls) -> Response:
        return cls(choices=[Choice(message=Message(content="{not-json"))])


class _Completions:
    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class Client:
    """Mock OpenAI-compatible client surface: ``chat.completions.create``."""

    def __init__(self, outcome: Any | None = None) -> None:
        self._completions = _Completions(Response() if outcome is None else outcome)
        self.chat = type("_Chat", (), {"completions": self._completions})()

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._completions.calls


class CountingEnvironmentReader:
    """Records env lookups without reading the real process environment."""

    def __init__(self, mapping: dict[str, str | None] | None = None) -> None:
        self.mapping = dict(mapping or {})
        self.calls: list[str] = []

    def __call__(self, name: str) -> str | None:
        self.calls.append(name)
        return self.mapping.get(name)


def sdk_exception(class_name: str, message: str = "synthetic") -> Exception:
    return type(class_name, (Exception,), {})(message)


def settings_for(
    provider: str = "openrouter",
    *,
    openrouter: dict[str, Any] | None = None,
    openai: dict[str, Any] | None = None,
    repository_path: str = ".",
) -> CodestrataSettings:
    payload: dict[str, Any] = {
        "repository": {"path": repository_path},
        "ai": {"provider": provider},
    }
    if openrouter is not None:
        payload["ai"]["openrouter"] = openrouter
    if openai is not None:
        payload["ai"]["openai"] = openai
    return CodestrataSettings.model_validate(payload)


def provider_request(*, model_id: str = TEST_ONLY_MODEL) -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=SYNTHETIC_INSTRUCTION,
            context_payload_text=SYNTHETIC_CONTEXT,
        ),
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        model_reference=ProviderModelReference(model_id),
        execution_options=ExecutionOptions(),
    )


def analysis_context() -> LLMAnalysisContext:
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
    context = analysis_context()
    return ModernizationModelRequest(
        prompt_request=ModernizationPromptBuilder().build(context),
        analysis_context=context,
    )


def invocation_options(*, model_id: str = TEST_ONLY_MODEL) -> ModelInvocationOptions:
    return ModelInvocationOptions(model_id=model_id)


def no_environment(_name: str) -> str | None:
    return None


def key_present_reader(name: str) -> str | None:
    if name == DEFAULT_API_KEY_ENV:
        return SYNTHETIC_API_KEY
    return None


def injected_environ(**overrides: str) -> dict[str, str]:
    """Build a fully synthetic environ — never copies real API-key values."""

    base = {
        DEFAULT_API_KEY_ENV: SYNTHETIC_API_KEY,
    }
    base.update(overrides)
    return base


def synthetic_bedrock_probe(*_args: Any, **_kwargs: Any) -> Any:
    """Network-free Bedrock probe stub for doctor report assembly."""

    from codestrata.ai.aws_config import AwsSessionProbe, ResolvedAwsConfig

    return AwsSessionProbe(
        ok=True,
        resolved=ResolvedAwsConfig(
            profile=None,
            region="us-east-1",
            source_profile="synthetic",
            source_region="synthetic",
        ),
        effective_region="us-east-1",
        credential_source="synthetic",
        detail="synthetic bedrock probe (verification)",
        guidance=None,
    )


__all__ = [
    "SYNTHETIC_API_KEY",
    "SYNTHETIC_APP_NAME",
    "SYNTHETIC_CONTEXT",
    "SYNTHETIC_INSTRUCTION",
    "SYNTHETIC_INVALID_BASE_URL",
    "SYNTHETIC_INVALID_SITE_URL",
    "SYNTHETIC_OPENAI_API_KEY",
    "SYNTHETIC_RESPONSE",
    "SYNTHETIC_SITE_URL",
    "Choice",
    "Client",
    "CountingEnvironmentReader",
    "Message",
    "Response",
    "Usage",
    "analysis_context",
    "injected_environ",
    "invocation_options",
    "key_present_reader",
    "model_request",
    "no_environment",
    "provider_request",
    "sdk_exception",
    "settings_for",
    "synthetic_bedrock_probe",
]
