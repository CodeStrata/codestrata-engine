"""Immutable contracts for the modernization assessment agent."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.ai.prompts.models import PromptBuildOptions
from codestrata.ai.providers.models import ModelInvocationMetadata, ModelInvocationOptions
from codestrata.ai.recommendations.models import AIRecommendationResult
from codestrata.ai.recommendations.validation import DeterministicRecommendationNormalizationRemoval

AGENT_NAME = "modernization_assessment"
AGENT_VERSION = "1.0.0"
DEFAULT_MAX_TOOL_CALLS = 20

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list[Any] | dict[str, Any]


class AgentExecutionStatus(StrEnum):
    """Terminal status for an agent run."""

    COMPLETED = "completed"
    FAILED = "failed"


class AgentStepType(StrEnum):
    """Types of recorded agent execution steps."""

    TOOL_CALL = "tool_call"
    PROMPT_BUILD = "prompt_build"
    MODEL_INVOCATION = "model_invocation"
    VALIDATION = "validation"


class AgentExecutionOptions(BaseModel):
    """Options controlling a modernization assessment agent run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_options: ModelInvocationOptions
    prompt_options: PromptBuildOptions = Field(default_factory=PromptBuildOptions)
    enabled_tool_names: tuple[str, ...] | None = None
    max_tool_calls: int = Field(default=DEFAULT_MAX_TOOL_CALLS, gt=0)

    @field_validator("enabled_tool_names")
    @classmethod
    def validate_enabled_tool_names(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            name = item.strip()
            if not name:
                raise ValueError("enabled_tool_names must not contain blank values")
            key = name.lower()
            if key in seen:
                raise ValueError(f"Duplicate enabled tool name: {name}")
            seen.add(key)
            cleaned.append(name)
        return tuple(cleaned)


class AgentExecutionStep(BaseModel):
    """One recorded step in an agent execution trace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence_number: int = Field(gt=0)
    step_type: AgentStepType
    name: str = Field(min_length=1)
    started_at_utc: datetime
    completed_at_utc: datetime
    latency_ms: float = Field(ge=0.0)
    success: bool
    input_summary: dict[str, JSONValue] = Field(default_factory=dict)
    output_summary: dict[str, JSONValue] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None

    @field_validator("started_at_utc", "completed_at_utc")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware UTC")
        return value


class AgentExecutionTrace(BaseModel):
    """Immutable execution trace for a modernization assessment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str = Field(min_length=1)
    agent_name: str = AGENT_NAME
    agent_version: str = AGENT_VERSION
    started_at_utc: datetime
    completed_at_utc: datetime
    total_latency_ms: float = Field(ge=0.0)
    status: AgentExecutionStatus
    steps: tuple[AgentExecutionStep, ...] = ()
    tool_call_count: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)

    @field_validator("agent_name")
    @classmethod
    def validate_agent_name(cls, value: str) -> str:
        if value != AGENT_NAME:
            raise ValueError(f"agent_name must be {AGENT_NAME}")
        return value

    @field_validator("agent_version")
    @classmethod
    def validate_agent_version(cls, value: str) -> str:
        if value != AGENT_VERSION:
            raise ValueError(f"agent_version must be {AGENT_VERSION}")
        return value

    @field_validator("started_at_utc", "completed_at_utc")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware UTC")
        return value


class ModernizationAssessmentResult(BaseModel):
    """Successful modernization assessment agent output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_result: AIRecommendationResult
    model_metadata: ModelInvocationMetadata
    trace: AgentExecutionTrace
    raw_model_response: str | None = None
    parsed_model_response: dict[str, Any] | None = None
    normalization_removals: tuple[DeterministicRecommendationNormalizationRemoval, ...] = ()
    prompt_template_version: str | None = None
    prompt_hash: str | None = None
    context_hash: str | None = None
