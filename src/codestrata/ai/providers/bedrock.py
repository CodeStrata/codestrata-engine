"""AWS Bedrock Runtime provider using the Converse API.

**Migrated (Epic 11, Slice 11.7).** This module is now a thin compatibility
wrapper. It remains the public assess-path class — same name, same
constructor signature, same registry key (``bedrock``, still the default
provider), same ``AIModelProvider.invoke()`` contract — but the wire work now
happens in ``codestrata.ai.provider_adapters.bedrock``, which implements the
``AIProvider`` protocol and runs under ``AIProviderExecutor``.

What one ``invoke()`` does:

1. folds the ``PromptRequest`` into a ``ModernizationAdvisorInput`` and wraps
   it in an ``AIProviderRequest`` (``legacy_bridge``);
2. builds the adapter and its executor with ``DEFAULT_RETRY_POLICY``
   (``maximum_attempts=1``, i.e. exactly one provider call per assess run)
   and ``DEFAULT_TIMEOUT_POLICY`` (60s, declarative — the real bound is still
   the botocore ``Config(connect_timeout=..., read_timeout=...)`` that
   ``aws_config`` builds, whose ``retries={"max_attempts": 1}`` is unchanged);
3. runs the executor, which never raises for an expected provider failure;
4. translates a non-SUCCESS outcome back into the *same* legacy exception
   type and message the pre-migration provider raised, so
   ``AiEnrichmentService``'s fail-soft behavior is unchanged;
5. on success, rebuilds ``ModelInvocationResult`` — including the enrichment
   payload short-circuit and the legacy ``AIRecommendationResult`` parse.

**Client construction is now lazy.** The pre-migration provider built the
Bedrock Runtime client in ``__init__``, so a missing ``boto3`` extra or an
unusable AWS profile raised ``AIProviderConfigurationError`` at construction
time. It is now built on the first ``invoke()`` instead, and the same
``AIProviderConfigurationError`` (with the same message) is raised from
there. Constructing a provider therefore never touches the AWS credential
chain, the instance metadata service, or STS. An injected ``client`` is used
as-is and ``aws_config`` is never called.

``build_converse_request``, ``split_prompt_for_converse``, and
``extract_converse_response`` remain importable from this module, delegating
to the adapter's mapping modules, because the Slice 11.1 baseline
verification and the existing provider tests characterize them here.
"""

from __future__ import annotations

import logging
from typing import Any

from codestrata.ai.aws_config import BedrockRuntimeClient
from codestrata.ai.prompts.models import PromptMessage, PromptRequest
from codestrata.ai.provider_adapters.bedrock import (
    legacy_bridge,
    request_mapping,
    response_mapping,
    usage_mapping,
)
from codestrata.ai.provider_adapters.bedrock.adapter import BedrockProvider
from codestrata.ai.provider_adapters.bedrock.error_mapping import classify_sdk_exception
from codestrata.ai.provider_adapters.bedrock.factory import (
    build_bedrock_executor,
    build_bedrock_provider,
)
from codestrata.ai.provider_adapters.bedrock.response_mapping import BedrockInvocationDetail
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
from codestrata.config.settings import CodestrataSettings

logger = logging.getLogger(__name__)

BEDROCK_PROVIDER_NAME = legacy_bridge.BEDROCK_PROVIDER_NAME


class BedrockAIModelProvider(AIModelProvider):
    """Invoke Bedrock text models through the standardized Converse API."""

    def __init__(
        self,
        *,
        client: BedrockRuntimeClient | None = None,
        region_name: str | None = None,
        profile_name: str | None = None,
        settings: CodestrataSettings | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        resolved_timeout = provider_timeout_seconds(
            settings,
            provider="bedrock",
            explicit=timeout_seconds,
        )
        if resolved_timeout <= 0:
            raise AIProviderConfigurationError("timeout_seconds must be positive")
        self._region_name = region_name
        self._profile_name = profile_name
        self._settings = settings
        self._timeout_seconds = resolved_timeout
        self._client = client

    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        """Invoke Bedrock Converse and return a validated recommendation result."""

        model_id = options.model_id.strip()
        if not model_id:
            raise AIProviderConfigurationError("model_id must be a nonempty string")

        self._log_invocation(model_id)

        details: list[BedrockInvocationDetail] = []
        adapter = build_bedrock_provider(
            settings=self._settings,
            profile_name=self._profile_name,
            region_name=self._region_name,
            timeout_seconds=self._timeout_seconds,
            client=self._client,
            detail_sink=details.append,
        )
        provider_request = legacy_bridge.build_provider_request(
            request.prompt_request,
            options,
            model_id=model_id,
        )

        execution = build_bedrock_executor(adapter).execute(provider_request)
        detail = details[-1] if details else BedrockInvocationDetail(latency_ms=0.0)

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
            # Modernization Advisor JSON — leave parsing to AiEnrichmentService.
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

    def _log_invocation(self, model_id: str) -> None:
        """Emit the informational invocation log, unchanged from pre-migration.

        This names the configured profile and region because operators rely
        on it when diagnosing credential problems. It is a log line only:
        every adapter diagnostic view and every verification report carries
        presence booleans instead (see ``provider_adapters/bedrock/
        diagnostics.py``).
        """

        logger.info(
            "Invoking Bedrock Converse model_id=%s profile=%s region=%s",
            model_id,
            self._resolved_profile_label(),
            self._region_name
            or (self._settings.aws.region if self._settings is not None else None)
            or "(default)",
        )

    def _resolved_profile_label(self) -> str:
        return self._configured_profile_name() or "(default)"

    def _configured_profile_name(self) -> str | None:
        return self._profile_name or (
            self._settings.aws.profile if self._settings is not None else None
        )

    def _legacy_error(
        self,
        execution: AIProviderExecutionResult,
        adapter: BedrockProvider,
        detail: BedrockInvocationDetail,
    ) -> AIProviderError:
        provider_result = execution.provider_result
        error = provider_result.error if provider_result is not None else None
        if error is None:
            return AIProviderInvocationError(
                "Bedrock invocation did not produce a usable response"
            )
        return legacy_bridge.legacy_error_for(
            error,
            profile_name=adapter.configuration.client_inputs.guidance_profile_name,
            legacy_detail=detail.legacy_error_detail,
            legacy_label=detail.legacy_error_label,
        )


def build_converse_request(
    prompt_request: PromptRequest,
    options: ModelInvocationOptions,
) -> dict[str, Any]:
    """Build a model-family-neutral Bedrock Converse request.

    Retained as a module-level helper (and kept byte-compatible) because the
    Slice 11.1 baseline verification characterizes this exact shape.
    """

    return request_mapping.build_converse_kwargs(
        legacy_bridge.build_provider_request(
            prompt_request, options, model_id=options.model_id.strip()
        )
    )


def split_prompt_for_converse(
    messages: list[PromptMessage],
) -> tuple[str, str]:
    """Separate system/developer instructions from the user context payload."""

    payload = legacy_bridge.fold_prompt_messages(messages)
    system_text = request_mapping.build_system_text(
        payload.instruction_text,
        response_expectation=ResponseExpectation.STRUCTURED_JSON,
    )
    return system_text, payload.context_payload_text


def extract_converse_response(
    response: Any,
) -> tuple[str, ModelUsage, str | None, str | None, float | None]:
    """Extract assistant text, usage, stop reason, request id, and reported latency.

    Raises the legacy ``AIProviderInvocationError`` on a malformed response,
    matching the pre-migration behavior the Slice 11.1 baseline
    characterizes. The adapter itself never raises here — it returns a
    bounded ``invalid_response`` failure instead.
    """

    outcome = response_mapping.extract_converse_response(response)
    if outcome.extracted is None:
        assert outcome.failure is not None
        raise legacy_bridge.legacy_error_for(
            outcome.failure.error,
            legacy_detail=outcome.failure.legacy_detail,
            legacy_label=outcome.failure.legacy_label,
        )
    extracted = outcome.extracted
    totals = usage_mapping.extract_raw_totals(extracted.usage_payload)
    usage = ModelUsage(
        input_tokens=totals.input_tokens,
        output_tokens=totals.output_tokens,
        total_tokens=totals.total_tokens,
    )
    return (
        extracted.text,
        usage,
        extracted.stop_reason,
        extracted.request_id,
        extracted.reported_latency_ms,
    )


def _extract_usage(usage_payload: Any) -> ModelUsage:
    """Normalize a Converse ``usage`` mapping into the legacy ``ModelUsage``.

    Kept as a module-level private helper because the Slice 11.1 baseline
    verification characterizes token extraction through this exact name.
    """

    totals = usage_mapping.extract_raw_totals(usage_payload)
    return ModelUsage(
        input_tokens=totals.input_tokens,
        output_tokens=totals.output_tokens,
        total_tokens=totals.total_tokens,
    )


def _map_bedrock_exception(
    error: Exception,
    *,
    profile: str | None = None,
) -> AIProviderError:
    """Map an AWS SDK exception onto the legacy exception the wrapper raises."""

    failure = classify_sdk_exception(error)
    return legacy_bridge.legacy_error_for(
        failure.error,
        profile_name=profile,
        legacy_detail=failure.legacy_detail,
        legacy_label=failure.legacy_label,
    )


__all__ = [
    "BEDROCK_PROVIDER_NAME",
    "BedrockAIModelProvider",
    "build_converse_request",
    "extract_converse_response",
    "split_prompt_for_converse",
]
