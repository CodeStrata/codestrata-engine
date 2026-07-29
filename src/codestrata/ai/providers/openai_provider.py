"""OpenAI Chat Completions provider for Modernization Advisor (assess enrichment)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from codestrata.ai.prompts.models import PromptRequest
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
from codestrata.config.settings import CodestrataSettings, OpenAISettings

logger = logging.getLogger(__name__)

OPENAI_PROVIDER_NAME = "openai"


class OpenAIAIModelProvider(AIModelProvider):
    """Invoke OpenAI (or Azure-compatible) chat completions for assess enrichment."""

    def __init__(
        self,
        *,
        settings: CodestrataSettings | None = None,
        openai_settings: OpenAISettings | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: Any | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise AIProviderConfigurationError("timeout_seconds must be positive")
        self._settings = settings
        self._openai = openai_settings or (
            settings.ai.openai if settings is not None else OpenAISettings()
        )
        self._timeout_seconds = timeout_seconds
        self._client = client

    def invoke(
        self,
        request: ModernizationModelRequest,
        options: ModelInvocationOptions,
    ) -> ModelInvocationResult:
        model_id = options.model_id.strip()
        if not model_id:
            raise AIProviderConfigurationError("model_id must be a nonempty string")

        client = self._client or self._build_client()
        messages = _chat_messages(request.prompt_request)
        logger.info("Invoking OpenAI chat completions model_id=%s", model_id)

        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=options.temperature,
                max_tokens=options.max_output_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as error:  # noqa: BLE001 - provider boundary
            raise _map_openai_exception(error) from error

        latency_ms = (time.perf_counter() - started) * 1000.0
        raw_response_text, usage, stop_reason, request_id = _extract_chat_response(response)
        metadata = ModelInvocationMetadata(
            provider=OPENAI_PROVIDER_NAME,
            model_id=model_id,
            request_id=options.request_id or request_id,
            latency_ms=latency_ms,
            usage=usage,
            stop_reason=stop_reason,
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

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise AIProviderConfigurationError(
                "OpenAI provider requires the optional 'openai' extra. "
                "Install with: pip install 'codestrata[openai]'"
            ) from error

        api_key_env = self._openai.api_key_env.strip() or "OPENAI_API_KEY"
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            raise AIProviderConfigurationError(
                f"OpenAI API key not found in environment variable {api_key_env}"
            )
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": self._timeout_seconds,
        }
        base_url = (self._openai.base_url or "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        try:
            return OpenAI(**kwargs)
        except Exception as error:  # noqa: BLE001
            raise AIProviderConfigurationError(
                "Failed to configure OpenAI client: " + sanitize_provider_text(str(error))
            ) from error


def _chat_messages(prompt_request: PromptRequest) -> list[dict[str, str]]:
    system_parts: list[str] = []
    user_parts: list[str] = []
    for message in prompt_request.messages:
        if message.role == "system":
            system_parts.append(message.content)
        elif message.role == "developer":
            system_parts.append(f"Developer instructions:\n{message.content}")
        elif message.role == "user":
            user_parts.append(message.content)
        else:  # pragma: no cover
            raise AIProviderConfigurationError(f"Unsupported prompt role: {message.role}")
    if not user_parts:
        raise AIProviderConfigurationError(
            "PromptRequest must include at least one user message with analysis context"
        )
    system_parts.append(
        "Respond with a single JSON object only. Do not include markdown fences or prose."
    )
    messages: list[dict[str, str]] = []
    system_text = "\n\n".join(part for part in system_parts if part.strip())
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append(
        {
            "role": "user",
            "content": "\n\n".join(part for part in user_parts if part.strip()),
        }
    )
    return messages


def _extract_chat_response(
    response: Any,
) -> tuple[str, ModelUsage, str | None, str | None]:
    try:
        choice = response.choices[0]
        content = choice.message.content
        if not isinstance(content, str) or not content.strip():
            raise AIProviderInvocationError("OpenAI response did not include assistant text")
        usage_obj = getattr(response, "usage", None)
        usage = ModelUsage(
            input_tokens=_optional_int(getattr(usage_obj, "prompt_tokens", None)),
            output_tokens=_optional_int(getattr(usage_obj, "completion_tokens", None)),
            total_tokens=_optional_int(getattr(usage_obj, "total_tokens", None)),
        )
        stop_reason = getattr(choice, "finish_reason", None)
        request_id = getattr(response, "id", None)
        return (
            content,
            usage,
            str(stop_reason) if stop_reason is not None else None,
            str(request_id) if request_id is not None else None,
        )
    except AIProviderError:
        raise
    except Exception as error:  # noqa: BLE001
        raise AIProviderInvocationError(
            "Failed to read OpenAI chat response: " + sanitize_provider_text(str(error))
        ) from error


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _map_openai_exception(error: Exception) -> AIProviderError:
    message = sanitize_provider_text(str(error))
    name = type(error).__name__
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return AIProviderInvocationError(
            "OpenAI authentication failed. Verify API key and model access. "
            f"Details: {message}"
        )
    if name in {"RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"}:
        return AIProviderTimeoutError(f"OpenAI temporary service failure: {message}")
    if name in {"BadRequestError", "NotFoundError", "UnprocessableEntityError"}:
        return AIProviderInvocationError(
            f"OpenAI invalid model or request configuration: {message}"
        )
    return AIProviderInvocationError(f"OpenAI invocation failed: {message}")


__all__ = [
    "OPENAI_PROVIDER_NAME",
    "OpenAIAIModelProvider",
]
