"""Immutable contracts for AI model provider invocation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codestrata.ai.contracts.models import LLMAnalysisContext
from codestrata.ai.prompts.models import PromptRequest
from codestrata.ai.recommendations.models import AIRecommendationResult
from codestrata.ai.recommendations.validation import DeterministicRecommendationNormalizationRemoval

DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_TEMPERATURE = 0.0


class ModelInvocationOptions(BaseModel):
    """Options controlling a single model invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, gt=0)
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0.0)
    request_id: str | None = None


class ModelUsage(BaseModel):
    """Token usage reported by a model provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelInvocationMetadata(BaseModel):
    """Structured metadata for a model invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    request_id: str | None = None
    latency_ms: float = Field(ge=0.0)
    usage: ModelUsage
    stop_reason: str | None = None


class ModelInvocationResult(BaseModel):
    """Raw model response plus optional legacy recommendation parse."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Legacy AI-REC contract (optional). Modernization Advisor path parses
    # ``AiEnrichmentResult`` from ``raw_response_text`` instead.
    recommendation_result: AIRecommendationResult | None = None
    metadata: ModelInvocationMetadata
    raw_response_text: str
    parsed_model_response: dict[str, Any] | None = None
    normalization_removals: tuple[DeterministicRecommendationNormalizationRemoval, ...] = ()


class ModernizationModelRequest(BaseModel):
    """Prompt package paired with the original analysis context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_request: PromptRequest
    analysis_context: LLMAnalysisContext
