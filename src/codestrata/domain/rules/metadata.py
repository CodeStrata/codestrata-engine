"""Immutable rule metadata for the Shared Rule Platform."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.rules.enums import RuleCategory, RuleIncrementalBehavior, RuleSeverity
from codestrata.domain.rules.identifiers import RuleId, validate_rule_id
from codestrata.domain.rules.rule_confidence import RuleConfidence


class RuleVersion(BaseModel):
    """Explicit comparable rule version (semantic major.minor.patch)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int = Field(ge=0)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: RuleVersion) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: RuleVersion) -> bool:
        return self == other or self < other

    @classmethod
    def parse(cls, value: str) -> RuleVersion:
        compact = require_nonblank(value, label="rule_version")
        parts = compact.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError("rule_version must be major.minor.patch")
        return cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))


class RuleMetadata(BaseModel):
    """Immutable validated metadata for one shared rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: RuleId
    version: RuleVersion
    title: str
    description: str
    category: RuleCategory
    default_severity: RuleSeverity
    confidence: RuleConfidence
    # Epic 5 Slice 5.13 — catalog reference (not an embedded policy object).
    severity_policy_id: str | None = None
    supported_languages: tuple[str, ...] = ()
    supported_repository_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    remediation_summary: str | None = None
    documentation_reference: str | None = None
    enabled_by_default: bool = True
    experimental: bool = False
    requires_enterprise_context: bool = False
    incremental_behaviors: tuple[RuleIncrementalBehavior, ...] = (
        RuleIncrementalBehavior.ALWAYS_RUN,
        RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
    )

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_rule_id(cls, value: object) -> RuleId:
        if isinstance(value, RuleId):
            return value
        return RuleId(validate_rule_id(str(value)))

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> RuleVersion | object:
        if isinstance(value, RuleVersion):
            return value
        if isinstance(value, str):
            return RuleVersion.parse(value)
        return value

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule metadata field")

    @field_validator(
        "supported_languages",
        "supported_repository_types",
        "tags",
        "incremental_behaviors",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator(
        "remediation_summary",
        "documentation_reference",
        "severity_policy_id",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional rule metadata field")

    @field_validator("supported_languages", "supported_repository_types", "tags", mode="after")
    @classmethod
    def normalize_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted({item.strip().lower() for item in value if item and item.strip()}))

    @model_validator(mode="after")
    def default_severity_policy_id(self) -> RuleMetadata:
        if self.severity_policy_id:
            return self
        # Catalog policy IDs are severity.{rule_id} for Shared Rules.
        # Frozen model: assign via object.__setattr__.
        object.__setattr__(self, "severity_policy_id", f"severity.{self.rule_id}")
        return self
