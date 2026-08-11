"""OpenRouter provider for Modernization Advisor (assess enrichment).

**Wired (Epic 11, Slice 11.10).** Thin compatibility wrapper over
``codestrata.ai.provider_adapters.openrouter`` + ``AIProviderExecutor``.
Registered in ``AssessAIProviderRegistry`` as ``openrouter`` (explicit only;
Bedrock remains the default).
"""

from __future__ import annotations

import logging
from typing import Any

from codestrata.ai.provider_adapters.openrouter import legacy_bridge
from codestrata.ai.provider_adapters.openrouter.adapter import OpenRouterProvider
from codestrata.ai.provider_adapters.openrouter.factory import (
    build_openrouter_executor,
    build_openrouter_provider,
)
from codestrata.ai.provider_adapters.openrouter.response_mapping import OpenRouterInvocationDetail
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.execution_models import AIProviderExecutionResult
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
    ModernizationModelRequest,
)
from codestrata.ai.providers.parsing import parse_recommendation_response
from codestrata.ai.providers.settings_policies import provider_timeout_seconds
from codestrata.config.settings import CodestrataSettings, OpenRouterSettings

logger = logging.getLogger(__name__)

OPENROUTER_PROVIDER_NAME = legacy_bridge.OPENROUTER_PROVIDER_NAME


class OpenRouterAIModelProvider(AIModelProvider):
    """Invoke OpenRouter chat completions for assess enrichment."""

    def __init__(
        self,
        *,
        settings: CodestrataSettings | None = None,
        openrouter_settings: OpenRouterSettings | None = None,
        timeout_seconds: float | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._openrouter = openrouter_settings or (
            settings.ai.openrouter if settings is not None else OpenRouterSettings()
        )
        resolved_timeout = provider_timeout_seconds(
            settings,
            provider="openrouter",
            explicit=timeout_seconds,
            provider_settings_timeout=self._openrouter.timeout_seconds,
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
            raise AIProviderConfigurationError(
                "OpenRouter model_id must be a nonempty string "
                "(set --model-id, CODESTRATA_OPENROUTER_MODEL_ID, or [ai.openrouter].model)"
            )

        details: list[OpenRouterInvocationDetail] = []
        adapter = build_openrouter_provider(
            openrouter_settings=self._openrouter,
            timeout_seconds=self._timeout_seconds,
            client=self._client,
            detail_sink=details.append,
        )
        provider_request = legacy_bridge.build_provider_request(
            request.prompt_request,
            options,
            model_id=model_id,
        )

        logger.info("Invoking OpenRouter chat completions")
        execution = build_openrouter_executor(adapter).execute(provider_request)
        detail = details[-1] if details else OpenRouterInvocationDetail(latency_ms=0.0)

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
        adapter: OpenRouterProvider,
        detail: OpenRouterInvocationDetail,
    ) -> AIProviderError:
        provider_result = execution.provider_result
        error = provider_result.error if provider_result is not None else None
        if error is None:
            return AIProviderInvocationError(
                "OpenRouter invocation did not produce a usable response"
            )
        return legacy_bridge.legacy_error_for(
            error,
            api_key_env_name=adapter.configuration.api_key_env_name,
            legacy_detail=detail.legacy_error_detail,
        )


__all__ = [
    "OPENROUTER_PROVIDER_NAME",
    "OpenRouterAIModelProvider",
]
