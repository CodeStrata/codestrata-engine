"""Immutable prompt package contracts for modernization assessment."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROMPT_SCHEMA_VERSION = "1.0.0"
PROMPT_PURPOSE = "modernization_assessment"
DEFAULT_PROMPT_TEMPLATE_VERSION = "1.0.0"
DEFAULT_MAX_CONTEXT_CHARACTERS = 200_000

PromptRole = Literal["system", "developer", "user"]


class PromptMessage(BaseModel):
    """A single ordered prompt message."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: PromptRole
    content: str = Field(min_length=1)


class PromptMetadata(BaseModel):
    """Deterministic metadata describing a built prompt package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_identifier: str = Field(min_length=1)
    context_schema_version: str = Field(min_length=1)
    recommendation_schema_version: str = Field(min_length=1)
    finding_count: int = Field(ge=0)
    technology_count: int = Field(ge=0)
    context_truncated: bool
    prompt_template_version: str = Field(min_length=1)


class PromptRequest(BaseModel):
    """Provider-neutral modernization assessment prompt package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = PROMPT_SCHEMA_VERSION
    purpose: str = PROMPT_PURPOSE
    messages: list[PromptMessage] = Field(min_length=1)
    context_json: str
    expected_output_schema_json: str
    metadata: PromptMetadata

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != PROMPT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {PROMPT_SCHEMA_VERSION}")
        return value

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: str) -> str:
        if value != PROMPT_PURPOSE:
            raise ValueError(f"purpose must be {PROMPT_PURPOSE}")
        return value


class PromptBuildOptions(BaseModel):
    """Configurable options for modernization prompt construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    include_context_json: bool = True
    include_output_schema: bool = True
    max_context_characters: int = Field(
        default=DEFAULT_MAX_CONTEXT_CHARACTERS,
        gt=0,
    )
    template_version: str = DEFAULT_PROMPT_TEMPLATE_VERSION

    @field_validator("template_version")
    @classmethod
    def validate_template_version(cls, value: str) -> str:
        compact = value.strip()
        if not compact:
            raise ValueError("template_version must be a nonempty string")
        return compact


class PromptBuildError(ValueError):
    """Raised when a prompt package cannot be constructed."""
