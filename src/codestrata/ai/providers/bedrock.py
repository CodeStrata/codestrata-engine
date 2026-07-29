"""AWS Bedrock Runtime provider using the Converse API."""

from __future__ import annotations

import logging
import time
from typing import Any

from codestrata.ai.aws_config import (
    AwsAuthenticationError,
    BedrockRuntimeClient,
    create_bedrock_runtime_client,
    format_aws_authentication_error,
)
from codestrata.ai.prompts.models import PromptMessage, PromptRequest
from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvocationError,
    AIProviderTimeoutError,
    AIResponseParsingError,
    AIResponseValidationError,
)
from codestrata.ai.providers.models import (
    DEFAULT_TIMEOUT_SECONDS,
    ModelInvocationMetadata,
    ModelInvocationOptions,
    ModelInvocationResult,
    ModelUsage,
    ModernizationModelRequest,
)
from codestrata.ai.providers.parsing import parse_recommendation_response, sanitize_provider_text
from codestrata.config.settings import CodestrataSettings

logger = logging.getLogger(__name__)

BEDROCK_PROVIDER_NAME = "bedrock"


class BedrockAIModelProvider(AIModelProvider):
    """Invoke Bedrock text models through the standardized Converse API."""

    def __init__(
        self,
        *,
        client: BedrockRuntimeClient | None = None,
        region_name: str | None = None,
        profile_name: str | None = None,
        settings: CodestrataSettings | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise AIProviderConfigurationError("timeout_seconds must be positive")
        self._region_name = region_name
        self._profile_name = profile_name
        self._settings = settings
        self._timeout_seconds = timeout_seconds
        if client is not None:
            self._client = client
        else:
            try:
                self._client = create_bedrock_runtime_client(
                    settings=settings,
                    profile=profile_name,
                    region=region_name,
                    timeout_seconds=timeout_seconds,
                )
            except AwsAuthenticationError as error:
                raise AIProviderConfigurationError(str(error)) from error
            except RuntimeError as error:
                raise AIProviderConfigurationError(sanitize_provider_text(str(error))) from error

    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        """Invoke Bedrock Converse and return a validated recommendation result."""

        model_id = options.model_id.strip()
        if not model_id:
            raise AIProviderConfigurationError("model_id must be a nonempty string")

        resolved_profile = (
            self._profile_name
            or (self._settings.aws.profile if self._settings is not None else None)
            or "(default)"
        )
        resolved_region = (
            self._region_name
            or (self._settings.aws.region if self._settings is not None else None)
            or "(default)"
        )
        logger.info(
            "Invoking Bedrock Converse model_id=%s profile=%s region=%s",
            model_id,
            resolved_profile,
            resolved_region,
        )

        converse_kwargs = build_converse_request(request.prompt_request, options)
        started = time.perf_counter()
        try:
            response = self._client.converse(**converse_kwargs)
        except AwsAuthenticationError as error:
            raise AIProviderInvocationError(str(error)) from error
        except Exception as error:  # noqa: BLE001 - provider boundary
            raise _map_bedrock_exception(
                error,
                profile=self._profile_name
                or (self._settings.aws.profile if self._settings is not None else None),
            ) from error

        measured_latency_ms = (time.perf_counter() - started) * 1000.0
        try:
            raw_response_text, usage, stop_reason, response_request_id, reported_latency = (
                extract_converse_response(response)
            )
        except AIProviderError:
            raise
        except Exception as error:  # noqa: BLE001 - provider boundary
            raise AIProviderInvocationError(
                "Failed to read Bedrock Converse response: " + sanitize_provider_text(str(error))
            ) from error

        latency_ms = (
            float(reported_latency) if reported_latency is not None else measured_latency_ms
        )
        request_id = options.request_id or response_request_id
        metadata = ModelInvocationMetadata(
            provider=BEDROCK_PROVIDER_NAME,
            model_id=model_id,
            request_id=request_id,
            latency_ms=latency_ms,
            usage=usage,
            stop_reason=stop_reason,
        )
        try:
            from codestrata.ai.enrichment.parsing import looks_like_enrichment_payload

            if looks_like_enrichment_payload(raw_response_text):
                # Modernization Advisor JSON — leave parsing to AiEnrichmentService.
                return ModelInvocationResult(
                    recommendation_result=None,
                    metadata=metadata,
                    raw_response_text=raw_response_text,
                )
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
        except Exception as error:  # noqa: BLE001 - provider boundary
            raise AIResponseParsingError(
                "Unexpected failure while parsing Bedrock response: "
                + sanitize_provider_text(str(error)),
                metadata=metadata,
                raw_response_text=raw_response_text,
                validation_details=str(error),
            ) from error

        return ModelInvocationResult(
            recommendation_result=parse_outcome.result,
            metadata=metadata,
            raw_response_text=raw_response_text,
            parsed_model_response=parse_outcome.parsed_model_response,
            normalization_removals=parse_outcome.normalization_removals,
        )


def build_converse_request(
    prompt_request: PromptRequest,
    options: ModelInvocationOptions,
) -> dict[str, Any]:
    """Build a model-family-neutral Bedrock Converse request."""

    system_text, user_text = split_prompt_for_converse(prompt_request.messages)
    request: dict[str, Any] = {
        "modelId": options.model_id.strip(),
        "messages": [
            {
                "role": "user",
                "content": [{"text": user_text}],
            }
        ],
        "inferenceConfig": {
            "maxTokens": options.max_output_tokens,
            "temperature": options.temperature,
        },
    }
    if system_text:
        request["system"] = [{"text": system_text}]
    return request


def split_prompt_for_converse(
    messages: list[PromptMessage],
) -> tuple[str, str]:
    """Separate system/developer instructions from the user context payload."""

    system_parts: list[str] = []
    user_parts: list[str] = []

    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
        elif message.role == "developer":
            system_parts.append(f"Developer instructions:\n{message.content}")
        elif message.role == "user":
            user_parts.append(message.content)
        else:  # pragma: no cover - Literal-protected
            raise AIProviderConfigurationError(f"Unsupported prompt role: {message.role}")

    if not user_parts:
        raise AIProviderConfigurationError(
            "PromptRequest must include at least one user message with analysis context"
        )

    system_parts.append(
        "Respond with a single JSON object only. Do not include markdown fences or prose."
    )
    system_text = "\n\n".join(part for part in system_parts if part.strip())
    user_text = "\n\n".join(part for part in user_parts if part.strip())
    if not user_text.strip():
        raise AIProviderConfigurationError("PromptRequest user message must be nonempty")
    return system_text, user_text


def extract_converse_response(
    response: Any,
) -> tuple[str, ModelUsage, str | None, str | None, float | None]:
    """Extract assistant text, usage, stop reason, request id, and reported latency."""

    if not isinstance(response, dict):
        raise AIProviderInvocationError("Bedrock Converse response must be a mapping")

    output = response.get("output")
    if not isinstance(output, dict):
        raise AIProviderInvocationError("Bedrock Converse response is missing output")

    message = output.get("message")
    if not isinstance(message, dict):
        raise AIProviderInvocationError("Bedrock Converse response is missing output.message")

    content = message.get("content")
    if not isinstance(content, list):
        raise AIProviderInvocationError(
            "Bedrock Converse response is missing output.message.content"
        )

    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            text_parts.append(text)

    if not text_parts:
        raise AIProviderInvocationError(
            "Bedrock Converse response did not include assistant text content"
        )

    raw_text = "".join(text_parts)
    usage = _extract_usage(response.get("usage"))
    stop_reason_value = response.get("stopReason")
    stop_reason = str(stop_reason_value) if stop_reason_value is not None else None
    request_id = _extract_request_id(response)
    reported_latency = _extract_reported_latency(response.get("metrics"))
    return raw_text, usage, stop_reason, request_id, reported_latency


def _extract_usage(usage_payload: Any) -> ModelUsage:
    if not isinstance(usage_payload, dict):
        return ModelUsage()
    input_tokens = _optional_non_negative_int(usage_payload.get("inputTokens"))
    output_tokens = _optional_non_negative_int(usage_payload.get("outputTokens"))
    total_tokens = _optional_non_negative_int(usage_payload.get("totalTokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return ModelUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _extract_reported_latency(metrics: Any) -> float | None:
    if not isinstance(metrics, dict):
        return None
    value = metrics.get("latencyMs")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _extract_request_id(response: dict[str, Any]) -> str | None:
    metadata = response.get("ResponseMetadata")
    if not isinstance(metadata, dict):
        return None
    request_id = metadata.get("RequestId")
    return str(request_id) if request_id is not None else None


def _optional_non_negative_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _map_bedrock_exception(
    error: Exception,
    *,
    profile: str | None = None,
) -> AIProviderError:
    message = sanitize_provider_text(str(error))
    error_name = type(error).__name__
    error_code = _client_error_code(error)

    if error_name in {
        "NoCredentialsError",
        "PartialCredentialsError",
        "ProfileNotFound",
        "UnauthorizedSSOTokenError",
        "TokenRetrievalError",
        "SSOTokenLoadError",
    }:
        return AIProviderInvocationError(format_aws_authentication_error(profile=profile))

    if error_name in {"ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError"}:
        return AIProviderTimeoutError(f"Bedrock invocation timed out: {message}")

    if error_code in {
        "UnrecognizedClientException",
        "InvalidSignatureException",
        "ExpiredTokenException",
        "AuthFailure",
    }:
        return AIProviderInvocationError(format_aws_authentication_error(profile=profile))

    if error_code in {"AccessDeniedException", "UnauthorizedOperation"}:
        return AIProviderInvocationError(
            "Bedrock model access denied. Verify IAM permissions for Bedrock "
            f"and the selected model. Details: {message}"
        )

    if error_code in {
        "ThrottlingException",
        "TooManyRequestsException",
        "ServiceQuotaExceededException",
        "ModelNotReadyException",
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelTimeoutException",
    }:
        return AIProviderTimeoutError(f"Bedrock temporary service failure: {message}")

    if error_code in {
        "ValidationException",
        "InvalidRequestException",
        "ResourceNotFoundException",
        "ModelNotSupportedException",
    }:
        return AIProviderInvocationError(
            f"Bedrock invalid model or request configuration: {message}"
        )

    if error_name in {"BotoCoreError", "ClientError"} or error_code:
        label = error_code or error_name
        return AIProviderInvocationError(f"Bedrock service error ({label}): {message}")

    return AIProviderInvocationError(f"Bedrock invocation failed: {message}")


def _client_error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    error_payload = response.get("Error")
    if not isinstance(error_payload, dict):
        return None
    code = error_payload.get("Code")
    return str(code) if code is not None else None
