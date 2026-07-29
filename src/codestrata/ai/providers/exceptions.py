"""Typed exceptions for CodeStrata optional AI model providers."""

from __future__ import annotations

from typing import Any

from codestrata.ai.providers.models import ModelInvocationMetadata


class AIProviderError(Exception):
    """Base error for AI model provider failures."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when a provider is misconfigured or unavailable."""


class AIProviderInvocationError(AIProviderError):
    """Raised when a provider invocation fails."""


class AIProviderTimeoutError(AIProviderInvocationError):
    """Raised when a provider invocation times out."""


class AIResponseContractError(AIProviderError):
    """Base for failures after a provider response was received."""

    def __init__(
        self,
        message: str,
        *,
        metadata: ModelInvocationMetadata | None = None,
        raw_response_text: str | None = None,
        parsed_payload: dict[str, Any] | None = None,
        validation_details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = metadata
        self.raw_response_text = raw_response_text
        self.parsed_payload = parsed_payload
        self.validation_details = validation_details or message


class AIResponseParsingError(AIResponseContractError):
    """Raised when a model response cannot be parsed as the required contract."""


class AIResponseValidationError(AIResponseContractError):
    """Raised when parsed model output fails contract or context validation."""
