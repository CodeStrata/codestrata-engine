"""Synthetic fixtures for SV.11.12 — no network, no real credentials, no waiting.

Distinctive privacy markers must never appear in PUBLIC artifacts (diagnostics,
doctor redacted views, verification reports). Private request objects may carry
prompt/model values; those are not treated as public.
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
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderModelReference
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)
from codestrata.ai.providers.models import ModelInvocationOptions, ModernizationModelRequest
from codestrata.config.settings import (
    BedrockSettings,
    CodestrataSettings,
    OpenAISettings,
    OpenRouterSettings,
)

# --- Forbidden synthetic markers (must never appear in PUBLIC artifacts) ---

SYNTHETIC_OPENAI_KEY = "sk-synth-openai-privacy-1112-never-real"
SYNTHETIC_OPENROUTER_KEY = "sk-synth-openrouter-privacy-1112"
SYNTHETIC_AWS_ACCESS = "AKIASYNTHPRIVACY1112TEST"
SYNTHETIC_AWS_SECRET = "synth/aws/secret/privacy1112xxxxxxxx"
SYNTHETIC_SESSION = "synth-session-token-privacy-1112"
SYNTHETIC_PROMPT = "SYNTHETIC_PRIVACY_PROMPT_MARKER_1112"
SYNTHETIC_RESPONSE = "SYNTHETIC_PRIVACY_RESPONSE_MARKER_1112"
SYNTHETIC_MODEL_OPENAI = "gpt-synth-privacy-1112-model"
SYNTHETIC_MODEL_BEDROCK = "amazon.synth-privacy-1112-v1:0"
SYNTHETIC_MODEL_OPENROUTER = "test-only/privacy-1112-model"
SYNTHETIC_REQUEST_ID = "req_synth_privacy_1112"
SYNTHETIC_BASE_URL = "https://synth-privacy-1112.example.invalid/v1"
SYNTHETIC_SITE_URL = "https://synth-site-privacy-1112.example.invalid"
SYNTHETIC_APP_NAME = "SynthAppPrivacy1112"
SYNTHETIC_PATH = "/Users/synthetic-privacy-1112/repo"
SYNTHETIC_PROFILE = "synth-privacy-1112-profile"
SYNTHETIC_REGION = "synth-privacy-1112-region"
SYNTHETIC_EXCEPTION = (
    f"synthetic privacy exception at {SYNTHETIC_PATH} containing "
    f"{SYNTHETIC_OPENAI_KEY} and {SYNTHETIC_PROMPT}"
)
SYNTHETIC_CONTEXT = '{"synthetic_privacy_context":"1112"}'
SYNTHETIC_ENRICHMENT_RESPONSE = (
    '{"executive_summary":{"overview":"'
    + SYNTHETIC_RESPONSE
    + '"},"themes":[],"priorities":[]}'
)

ALL_FORBIDDEN_MARKERS: tuple[str, ...] = (
    SYNTHETIC_OPENAI_KEY,
    SYNTHETIC_OPENROUTER_KEY,
    SYNTHETIC_AWS_ACCESS,
    SYNTHETIC_AWS_SECRET,
    SYNTHETIC_SESSION,
    SYNTHETIC_PROMPT,
    SYNTHETIC_RESPONSE,
    SYNTHETIC_MODEL_OPENAI,
    SYNTHETIC_MODEL_BEDROCK,
    SYNTHETIC_MODEL_OPENROUTER,
    SYNTHETIC_REQUEST_ID,
    SYNTHETIC_BASE_URL,
    SYNTHETIC_SITE_URL,
    SYNTHETIC_APP_NAME,
    SYNTHETIC_PATH,
    SYNTHETIC_PROFILE,
    SYNTHETIC_REGION,
    SYNTHETIC_EXCEPTION,
    "Authorization: Bearer",
    "HTTP-Referer",
    "X-Title",
    "Traceback",
)


# --- OpenAI-compatible mock client ---


@dataclass
class Usage:
    prompt_tokens: Any = 2
    completion_tokens: Any = 3
    total_tokens: Any = 5


@dataclass
class Message:
    content: Any = SYNTHETIC_ENRICHMENT_RESPONSE


@dataclass
class Choice:
    message: Message = field(default_factory=Message)
    finish_reason: Any = "stop"


@dataclass
class OpenAIStyleResponse:
    choices: list[Choice] = field(default_factory=lambda: [Choice()])
    usage: Any = field(default_factory=Usage)
    id: Any = SYNTHETIC_REQUEST_ID

    @classmethod
    def empty(cls) -> OpenAIStyleResponse:
        return cls(choices=[Choice(message=Message(content="   "))])

    @classmethod
    def malformed(cls) -> OpenAIStyleResponse:
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


class OpenAIStyleClient:
    """Mock OpenAI/OpenRouter surface: ``chat.completions.create``."""

    def __init__(self, outcome: Any | None = None) -> None:
        self._completions = _Completions(
            OpenAIStyleResponse() if outcome is None else outcome
        )
        self.chat = type("_Chat", (), {"completions": self._completions})()

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._completions.calls


# --- Bedrock mock client ---


class BedrockClient:
    """Mock Bedrock surface: ``converse(**kwargs)``."""

    def __init__(self, outcome: Any | None = None) -> None:
        self._outcome = converse_response() if outcome is None else outcome
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def converse_response(
    text: Any = SYNTHETIC_ENRICHMENT_RESPONSE,
    *,
    request_id: str | None = SYNTHETIC_REQUEST_ID,
) -> dict[str, Any]:
    blocks = [{"text": item} for item in ([text] if isinstance(text, str) else text)]
    response: dict[str, Any] = {
        "output": {"message": {"role": "assistant", "content": blocks}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 2, "outputTokens": 3},
    }
    if request_id is not None:
        response["ResponseMetadata"] = {"RequestId": request_id}
    return response


def sdk_exception(class_name: str, message: str = SYNTHETIC_EXCEPTION) -> Exception:
    return type(class_name, (Exception,), {})(message)


def bedrock_client_error(code: str, message: str = SYNTHETIC_EXCEPTION) -> Exception:
    error = type("ClientError", (Exception,), {})(message)
    error.response = {  # type: ignore[attr-defined]
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"RequestId": SYNTHETIC_REQUEST_ID},
    }
    return error


class CountingEnvironmentReader:
    def __init__(self, mapping: dict[str, str | None] | None = None) -> None:
        self.mapping = dict(mapping or {})
        self.calls: list[str] = []

    def __call__(self, name: str) -> str | None:
        self.calls.append(name)
        return self.mapping.get(name)


def settings_for(
    provider: str = "bedrock",
    *,
    openai: dict[str, Any] | None = None,
    openrouter: dict[str, Any] | None = None,
    bedrock: dict[str, Any] | None = None,
    repository_path: str = ".",
) -> CodestrataSettings:
    payload: dict[str, Any] = {
        "repository": {"path": repository_path},
        "ai": {"provider": provider},
    }
    if openai is not None:
        payload["ai"]["openai"] = openai
    if openrouter is not None:
        payload["ai"]["openrouter"] = openrouter
    if bedrock is not None:
        payload["ai"]["bedrock"] = bedrock
    return CodestrataSettings.model_validate(payload)


def openai_settings_secret() -> OpenAISettings:
    return OpenAISettings(
        api_key_env="SYNTHETIC_PRIVACY_OPENAI_KEY_VAR",
        base_url=SYNTHETIC_BASE_URL,
        answer_model=SYNTHETIC_MODEL_OPENAI,
    )


def openrouter_settings_secret() -> OpenRouterSettings:
    return OpenRouterSettings(
        model=SYNTHETIC_MODEL_OPENROUTER,
        api_key_env="SYNTHETIC_PRIVACY_OPENROUTER_KEY_VAR",
        base_url=SYNTHETIC_BASE_URL,
        site_url=SYNTHETIC_SITE_URL,
        app_name=SYNTHETIC_APP_NAME,
    )


def bedrock_settings_secret() -> BedrockSettings:
    return BedrockSettings(model_id=SYNTHETIC_MODEL_BEDROCK, region=SYNTHETIC_REGION)


def provider_request(*, model_id: str, prompt: str = SYNTHETIC_PROMPT) -> AIProviderRequest:
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=prompt,
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
            name="synthetic-privacy-repository", source_type="github", file_count=1
        ),
        metrics=LLMMetricsContext(finding_count=1, technology_count=0),
        findings=[
            LLMFindingEvidence(
                rule_id="PRIV1112",
                title="Synthetic privacy finding",
                category="security",
                severity="high",
                summary="Synthetic privacy summary.",
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


def invocation_options(*, model_id: str) -> ModelInvocationOptions:
    return ModelInvocationOptions(model_id=model_id)


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


def leaked_markers(rendered: str, markers: tuple[str, ...] | None = None) -> list[str]:
    tokens = markers if markers is not None else ALL_FORBIDDEN_MARKERS
    return sorted(token for token in tokens if token in rendered)


def canonical_json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, default=str)


__all__ = [
    "ALL_FORBIDDEN_MARKERS",
    "BedrockClient",
    "Choice",
    "CountingEnvironmentReader",
    "Message",
    "OpenAIStyleClient",
    "OpenAIStyleResponse",
    "SYNTHETIC_APP_NAME",
    "SYNTHETIC_AWS_ACCESS",
    "SYNTHETIC_AWS_SECRET",
    "SYNTHETIC_BASE_URL",
    "SYNTHETIC_CONTEXT",
    "SYNTHETIC_ENRICHMENT_RESPONSE",
    "SYNTHETIC_EXCEPTION",
    "SYNTHETIC_MODEL_BEDROCK",
    "SYNTHETIC_MODEL_OPENAI",
    "SYNTHETIC_MODEL_OPENROUTER",
    "SYNTHETIC_OPENAI_KEY",
    "SYNTHETIC_OPENROUTER_KEY",
    "SYNTHETIC_PATH",
    "SYNTHETIC_PROFILE",
    "SYNTHETIC_PROMPT",
    "SYNTHETIC_REGION",
    "SYNTHETIC_REQUEST_ID",
    "SYNTHETIC_RESPONSE",
    "SYNTHETIC_SESSION",
    "SYNTHETIC_SITE_URL",
    "Usage",
    "analysis_context",
    "bedrock_client_error",
    "bedrock_settings_secret",
    "canonical_json",
    "converse_response",
    "invocation_options",
    "leaked_markers",
    "model_request",
    "openai_settings_secret",
    "openrouter_settings_secret",
    "provider_request",
    "sdk_exception",
    "settings_for",
    "synthetic_bedrock_probe",
]
