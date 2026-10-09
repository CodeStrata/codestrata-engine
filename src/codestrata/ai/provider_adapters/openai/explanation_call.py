"""One OpenAI explanation call. Contract types stay inside the migrated adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from codestrata.ai.provider_adapters.openai.factory import build_openai_provider
from codestrata.ai.provider_contracts.capabilities import ModernizationAdvisorInput
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import (
    AIProviderRequest,
    ExecutionOptions,
    ResponseExpectation,
)

ProviderFactory = Callable[[], object]


@dataclass(frozen=True, slots=True)
class OpenAIExplanationCall:
    """Adapter result without exposing provider-contract types to callers."""

    called: bool
    status: str
    error_code: str | None = None
    error_category: str | None = None
    error_detail: str | None = None
    payload: dict[str, object] | None = None


def run_openai_explanation(
    *,
    provider: object | None,
    provider_factory: ProviderFactory | None,
    model: str,
    permitted_evidence_ids: tuple[str, ...],
    instruction: str,
) -> OpenAIExplanationCall:
    """Execute one retained OpenAI explanation request, or report why it did not run."""

    active = provider if provider is not None else (provider_factory or build_openai_provider)()
    provider_id = getattr(active, "provider_id", None)
    if provider_id is not ProviderId.OPENAI:
        return OpenAIExplanationCall(called=False, status="unsupported_provider")
    supports = getattr(active, "supports", None)
    if not callable(supports) or not supports(CapabilityId.MODERNIZATION_ADVISOR):
        return OpenAIExplanationCall(called=False, status="unsupported_capability")
    try:
        request = _build_request(model, permitted_evidence_ids, instruction)
    except ProviderContractValidationError:
        return OpenAIExplanationCall(called=False, status="request_invalid")

    execute = getattr(active, "execute", None)
    if not callable(execute):
        return OpenAIExplanationCall(called=False, status="unsupported_capability")
    result = execute(request)
    status = getattr(result, "status", None)
    error = getattr(result, "error", None)
    if status is not ProviderExecutionStatus.SUCCESS or error is not None:
        return OpenAIExplanationCall(
            called=True,
            status="failed",
            error_code=getattr(error, "code", None) or "provider_explanation_failed",
            error_category=getattr(getattr(error, "category", None), "value", None) or "provider",
            error_detail=getattr(error, "detail", None) or "The explanation provider failed.",
        )
    content = getattr(result, "content", None)
    payload = getattr(content, "structured_payload", None)
    if not isinstance(payload, dict):
        return OpenAIExplanationCall(called=True, status="unreadable")
    return OpenAIExplanationCall(called=True, status="success", payload=payload)


def _build_request(
    model: str,
    permitted_evidence_ids: tuple[str, ...],
    instruction: str,
) -> AIProviderRequest:
    context = json.dumps(
        {"permitted_evidence_ids": list(permitted_evidence_ids)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return AIProviderRequest(
        capability=CapabilityId.MODERNIZATION_ADVISOR,
        payload=ModernizationAdvisorInput(
            instruction_text=instruction,
            context_payload_text=context,
        ),
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
        model_reference=ProviderModelReference(model),
        execution_options=ExecutionOptions(temperature=0.0, max_tokens=1024, timeout_seconds=30.0),
    )


__all__ = ["OpenAIExplanationCall", "run_openai_explanation"]
