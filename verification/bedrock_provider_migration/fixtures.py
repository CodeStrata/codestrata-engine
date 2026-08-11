"""Synthetic, in-memory fixtures. No AWS, no credentials, no waiting.

Every "Converse response" and "AWS SDK exception" in this suite is built here
from plain Python objects. The adapter classifies SDK failures by exception
*class name* and by ``response["Error"]["Code"]``, so :func:`sdk_exception`
and :func:`client_error` can exercise the real classification path without
``boto3`` being installed, without an AWS credential, and without any HTTP
traffic, instance metadata lookup, or STS call.

:class:`Client` exposes exactly one method — ``converse`` — because that is
the entire surface the adapter touches.
"""

from __future__ import annotations

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
from verification.bedrock_provider_migration.contract import BEDROCK_DEFAULT_MODEL_ID

SYNTHETIC_INSTRUCTION = "Synthetic instruction text."
SYNTHETIC_DEVELOPER = "Synthetic developer text."
SYNTHETIC_CONTEXT = '{"synthetic": true}'
# Enrichment-shaped so the compatibility wrapper short-circuits legacy
# AIRecommendationResult parsing (same pattern production uses for Advisor JSON).
SYNTHETIC_RESPONSE_TEXT = (
    '{"executive_summary": {"headline": "H", "narrative": "N"}, "themes": []}'
)
SYNTHETIC_REQUEST_ID = "synthetic-request-id"
SYNTHETIC_STOP_REASON = "end_turn"


class Client:
    """The only surface the adapter touches: ``converse(**kwargs)``."""

    def __init__(self, outcome: Any | None = None) -> None:
        self._outcome = converse_response() if outcome is None else outcome
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def converse_response(
    text: Any = SYNTHETIC_RESPONSE_TEXT,
    *,
    input_tokens: int | None = 11,
    output_tokens: int | None = 22,
    total_tokens: int | None = None,
    stop_reason: str | None = SYNTHETIC_STOP_REASON,
    request_id: str | None = SYNTHETIC_REQUEST_ID,
    latency_ms: float | None = None,
    include_usage: bool = True,
) -> dict[str, Any]:
    """Build a Converse response with the same shape the service returns."""

    blocks = [{"text": item} for item in ([text] if isinstance(text, str) else text)]
    response: dict[str, Any] = {
        "output": {"message": {"role": "assistant", "content": blocks}},
    }
    if stop_reason is not None:
        response["stopReason"] = stop_reason
    if request_id is not None:
        response["ResponseMetadata"] = {"RequestId": request_id}
    if include_usage:
        usage: dict[str, Any] = {}
        if input_tokens is not None:
            usage["inputTokens"] = input_tokens
        if output_tokens is not None:
            usage["outputTokens"] = output_tokens
        if total_tokens is not None:
            usage["totalTokens"] = total_tokens
        response["usage"] = usage
    if latency_ms is not None:
        response["metrics"] = {"latencyMs": latency_ms}
    return response


def sdk_exception(class_name: str, message: str = "synthetic failure") -> Exception:
    """Build an exception whose class name matches a botocore exception."""

    return type(class_name, (Exception,), {})(message)


def client_error(code: str, message: str = "synthetic failure") -> Exception:
    """Build a synthetic ``ClientError`` stand-in carrying an AWS error code."""

    error = type("ClientError", (Exception,), {})(message)
    error.response = {  # type: ignore[attr-defined]
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"RequestId": "synthetic-error-request-id"},
    }
    return error


def aws_authentication_error(message: str = "synthetic AWS guidance") -> Exception:
    """Build a stand-in whose class name matches ``AwsAuthenticationError``."""

    return type("AwsAuthenticationError", (RuntimeError,), {})(message)


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
    model_id: str = BEDROCK_DEFAULT_MODEL_ID,
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
    *, model_id: str = BEDROCK_DEFAULT_MODEL_ID, request_id: str | None = None
) -> ModelInvocationOptions:
    return ModelInvocationOptions(model_id=model_id, request_id=request_id)


__all__ = [
    "SYNTHETIC_CONTEXT",
    "SYNTHETIC_DEVELOPER",
    "SYNTHETIC_INSTRUCTION",
    "SYNTHETIC_REQUEST_ID",
    "SYNTHETIC_RESPONSE_TEXT",
    "SYNTHETIC_STOP_REASON",
    "Client",
    "advisor_payload",
    "analysis_context",
    "aws_authentication_error",
    "client_error",
    "converse_response",
    "invocation_options",
    "model_request",
    "prompt_request",
    "provider_request",
    "sdk_exception",
]
