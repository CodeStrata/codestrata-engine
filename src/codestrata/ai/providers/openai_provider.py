"""OpenAI provider for Modernization Advisor (assess enrichment).

**Migrated (Epic 11, Slice 11.6).** This module is now a thin compatibility
wrapper. It remains the public assess-path class — same name, same
constructor signature, same registry key (``openai``), same
``AIModelProvider.invoke()`` contract — but the wire work now happens in
``codestrata.ai.provider_adapters.openai``, which implements the
``AIProvider`` protocol and runs under ``AIProviderExecutor``.

What one ``invoke()`` does:

1. folds the ``PromptRequest`` into a ``ModernizationAdvisorInput`` and wraps
   it in an ``AIProviderRequest`` (``legacy_bridge``);
2. builds the adapter and its executor with ``DEFAULT_RETRY_POLICY``
   (``maximum_attempts=1``, i.e. exactly one provider call per assess run)
   and ``DEFAULT_TIMEOUT_POLICY`` (60s, declarative — the real bound is still
   the OpenAI client's own ``timeout=``);
3. runs the executor, which never raises for an expected provider failure;
4. translates a non-SUCCESS outcome back into the *same* legacy exception
   type and message the pre-migration provider raised, so
   ``AiEnrichmentService``'s fail-soft behavior is unchanged;
5. on success, rebuilds ``ModelInvocationResult`` — including the enrichment
   payload short-circuit and the legacy ``AIRecommendationResult`` parse.

Bedrock is migrated separately in Slice 11.7
(``codestrata.ai.provider_adapters.bedrock``). See
``engine/docs/ai-provider-openai.md`` and
``engine/docs/ai-provider-bedrock.md``.
"""

from __future__ import annotations

import logging
from typing import Any

from codestrata.ai.prompts.models import PromptRequest
from codestrata.ai.provider_adapters.openai import (
    legacy_bridge,
    request_mapping,
    response_mapping,
    usage_mapping,
)
from codestrata.ai.provider_adapters.openai.adapter import OpenAIProvider
from codestrata.ai.provider_adapters.openai.error_mapping import classify_sdk_exception
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_adapters.openai.response_mapping import OpenAIInvocationDetail
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.execution_models import AIProviderExecutionResult
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvocationError,
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import (
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
)
from codestrata.ai.providers.parsing import parse_recommendation_response
from codestrata.ai.providers.settings_policies import provider_timeout_seconds
from codestrata.config.settings import CodestrataSettings, OpenAISettings

logger = logging.getLogger(__name__)

OPENAI_PROVIDER_NAME = legacy_bridge.OPENAI_PROVIDER_NAME


class OpenAIAIModelProvider(AIModelProvider):
    """Invoke OpenAI (or Azure-compatible) chat completions for assess enrichment."""

    def __init__(
        self,
        *,
        settings: CodestrataSettings | None = None,
        openai_settings: OpenAISettings | None = None,
        timeout_seconds: float | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._openai = openai_settings or (
            settings.ai.openai if settings is not None else OpenAISettings()
        )
        resolved_timeout = provider_timeout_seconds(
            settings,
            provider="openai",
            explicit=timeout_seconds,
            provider_settings_timeout=self._openai.timeout_seconds,
        )
        if resolved_timeout <= 0:
            raise AIProviderConfigurationError("timeout_seconds must be positive")
        self._timeout_seconds = resolved_timeout
        self._client = client

    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        model_id = options.model_id.strip()
        if not model_id:
            raise AIProviderConfigurationError("model_id must be a nonempty string")

        details: list[OpenAIInvocationDetail] = []
        adapter = build_openai_provider(
            openai_settings=self._openai,
            timeout_seconds=self._timeout_seconds,
            client=self._client,
            detail_sink=details.append,
        )
        provider_request = legacy_bridge.build_provider_request(
            request.prompt_request,
            options,
            model_id=model_id,
        )

        logger.info("Invoking OpenAI chat completions model_id=%s", model_id)
        execution = build_openai_executor(adapter).execute(provider_request)
        detail = details[-1] if details else OpenAIInvocationDetail(latency_ms=0.0)

        if execution.status is not ProviderExecutionStatus.SUCCESS:
            raise self._legacy_error(execution, adapter, detail)

        provider_result = execution.provider_result
        assert provider_result is not None and provider_result.content is not None
        raw_response_text = provider_result.content.text or ""
        metadata = legacy_bridge.build_model_invocation_metadata(
            model_id=model_id,
            detail=detail,
            request_id_override=options.request_id,
        )

        from codestrata.ai.enrichment.parsing import looks_like_enrichment_payload

        if looks_like_enrichment_payload(raw_response_text):
            return ModelInvocationResult(
                recommendation_result=None,
                metadata=metadata,
                raw_response_text=raw_response_text,
            )

        try:
            parse_outcome = parse_recommendation_response(
                raw_response_text,
                request.analysis_context,
            )
        except AIResponseParsingError as error:
            raise AIResponseParsingError(
                str(error),
                metadata=metadata,
                raw_response_text=raw_response_text,
                parsed_payload=error.parsed_payload,
                validation_details=error.validation_details,
            ) from error
        except AIResponseValidationError as error:
            raise AIResponseValidationError(
                str(error),
                metadata=metadata,
                raw_response_text=raw_response_text,
                parsed_payload=error.parsed_payload,
                validation_details=error.validation_details,
            ) from error

        return ModelInvocationResult(
            recommendation_result=parse_outcome.result,
            metadata=metadata,
            raw_response_text=raw_response_text,
            parsed_model_response=parse_outcome.parsed_model_response,
            normalization_removals=parse_outcome.normalization_removals,
        )

    @staticmethod
    def _legacy_error(
        execution: AIProviderExecutionResult,
        adapter: OpenAIProvider,
        detail: OpenAIInvocationDetail,
    ) -> AIProviderError:
        provider_result = execution.provider_result
        error = provider_result.error if provider_result is not None else None
        if error is None:
            return AIProviderInvocationError(
                "OpenAI invocation did not produce a usable response"
            )
        return legacy_bridge.legacy_error_for(
            error,
            api_key_env_name=adapter.configuration.api_key_env_name,
            legacy_detail=detail.legacy_error_detail,
        )


def _chat_messages(prompt_request: PromptRequest) -> list[dict[str, str]]:
    """Build the Chat Completions message array for ``prompt_request``.

    Retained as a module-level helper (and kept byte-compatible) because the
    Slice 11.1 baseline verification characterizes this exact shape.
    """

    return request_mapping.build_chat_messages(
        legacy_bridge.fold_prompt_request(prompt_request),
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
    )


def _extract_chat_response(
    response: Any,
) -> tuple[str, ModelUsage, str | None, str | None]:
    """Read assistant text, usage, stop reason, and request ID off an SDK response.

    Raises the legacy ``AIProviderInvocationError`` on a malformed response,
    matching the pre-migration behavior the Slice 11.1 baseline
    characterizes. The adapter itself never raises here — it returns a
    bounded ``invalid_response`` failure instead.
    """

    outcome = response_mapping.extract_chat_response(response)
    if outcome.extracted is None:
        assert outcome.failure is not None
        raise legacy_bridge.legacy_error_for(
            outcome.failure.error,
            legacy_detail=outcome.failure.legacy_detail,
        )
    extracted = outcome.extracted
    totals = usage_mapping.extract_raw_totals(extracted.usage_object)
    usage = ModelUsage(
        input_tokens=totals.input_tokens,
        output_tokens=totals.output_tokens,
        total_tokens=totals.total_tokens,
    )
    return extracted.text, usage, extracted.stop_reason, extracted.request_id


def _map_openai_exception(error: Exception) -> AIProviderError:
    """Map an OpenAI SDK exception onto the legacy exception the wrapper raises."""

    failure = classify_sdk_exception(error)
    return legacy_bridge.legacy_error_for(failure.error, legacy_detail=failure.legacy_detail)


__all__ = [
    "OPENAI_PROVIDER_NAME",
    "OpenAIAIModelProvider",
]
