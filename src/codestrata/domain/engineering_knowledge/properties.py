"""Typed property models for Engineering Knowledge Graph nodes.

Shared metadata describes reusable concepts. Version fields record known facts
but do not alter canonical identities such as ``ekg:framework:spring-boot``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.engineering_knowledge.enums import (
    KnowledgeMaturityLevel,
    KnowledgeRuleKind,
    KnowledgeSeverity,
    ModernizationStrategyKind,
    TechnologyLifecycleStatus,
)
from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank

_URL_USERINFO = re.compile(r"://[^/\s]*@")


def _normalize_string_bag(value: object, *, label: str) -> tuple[str, ...]:
    items = as_tuple(value)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        compact = normalize_canonical_key(str(item))
        if compact in seen:
            continue
        seen.add(compact)
        cleaned.append(compact)
    return tuple(sorted(cleaned))


def _reject_credentialed_reference(value: str, *, label: str) -> str:
    compact = require_nonblank(value, label=label)
    if _URL_USERINFO.search(compact):
        raise ValueError(f"{label} must not contain credentials or access tokens")
    return compact


class _KnowledgePropertyModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def to_properties(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class EngineeringKnowledgeProperties(_KnowledgePropertyModel):
    """Shared metadata for reusable engineering knowledge nodes."""

    canonical_key: str
    name: str
    description: str | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    external_references: tuple[str, ...] = ()
    active: bool = True
    knowledge_version: str | None = None

    @field_validator("canonical_key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return normalize_canonical_key(str(value))

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="name")

    @field_validator("description", "knowledge_version", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional knowledge field")

    @field_validator("aliases", "tags", mode="before")
    @classmethod
    def normalize_bags(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="knowledge bag field")

    @field_validator("external_references", mode="before")
    @classmethod
    def normalize_references(cls, value: object) -> tuple[str, ...]:
        items = as_tuple(value)
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in items:
            compact = _reject_credentialed_reference(str(item), label="external_references")
            if compact in seen:
                continue
            seen.add(compact)
            cleaned.append(compact)
        return tuple(sorted(cleaned))


class TechnologyProperties(EngineeringKnowledgeProperties):
    category: str | None = None
    vendor: str | None = None
    lifecycle_status: TechnologyLifecycleStatus = TechnologyLifecycleStatus.UNKNOWN
    latest_known_version: str | None = None
    minimum_supported_version: str | None = None
    end_of_support_date: date | None = None

    @field_validator(
        "category",
        "vendor",
        "latest_known_version",
        "minimum_supported_version",
        mode="before",
    )
    @classmethod
    def normalize_optional_tech_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional technology field")


class FrameworkProperties(EngineeringKnowledgeProperties):
    ecosystem: str | None = None
    vendor: str | None = None
    lifecycle_status: TechnologyLifecycleStatus = TechnologyLifecycleStatus.UNKNOWN
    latest_known_version: str | None = None

    @field_validator("ecosystem", "vendor", "latest_known_version", mode="before")
    @classmethod
    def normalize_optional_framework_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional framework field")


class LanguageProperties(EngineeringKnowledgeProperties):
    paradigm: tuple[str, ...] = ()
    compiled: bool | None = None
    managed_runtime: bool | None = None

    @field_validator("paradigm", mode="before")
    @classmethod
    def normalize_paradigm(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="paradigm")


class ArchitectureStyleProperties(EngineeringKnowledgeProperties):
    benefits: tuple[str, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    suitable_for: tuple[str, ...] = ()

    @field_validator("benefits", "tradeoffs", "suitable_for", mode="before")
    @classmethod
    def normalize_bags(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="architecture style bag")


class PatternProperties(EngineeringKnowledgeProperties):
    intent: str | None = None
    benefits: tuple[str, ...] = ()
    liabilities: tuple[str, ...] = ()
    applicability: tuple[str, ...] = ()

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="intent")

    @field_validator("benefits", "liabilities", "applicability", mode="before")
    @classmethod
    def normalize_bags(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="pattern bag")


class QualityAttributeProperties(EngineeringKnowledgeProperties):
    definition: str
    common_metrics: tuple[str, ...] = ()
    common_tactics: tuple[str, ...] = ()

    @field_validator("definition", mode="before")
    @classmethod
    def normalize_definition(cls, value: object) -> str:
        return require_nonblank(str(value), label="definition")

    @field_validator("common_metrics", "common_tactics", mode="before")
    @classmethod
    def normalize_bags(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="quality attribute bag")


class EngineeringPracticeProperties(EngineeringKnowledgeProperties):
    maturity_level: KnowledgeMaturityLevel | None = None
    outcomes: tuple[str, ...] = ()

    @field_validator("outcomes", mode="before")
    @classmethod
    def normalize_outcomes(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="outcomes")


class RiskTypeProperties(EngineeringKnowledgeProperties):
    default_severity: KnowledgeSeverity | None = None
    causes: tuple[str, ...] = ()
    consequences: tuple[str, ...] = ()

    @field_validator("causes", "consequences", mode="before")
    @classmethod
    def normalize_bags(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="risk bag")


class ModernizationStrategyProperties(EngineeringKnowledgeProperties):
    strategy_kind: ModernizationStrategyKind = ModernizationStrategyKind.UNKNOWN
    benefits: tuple[str, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()

    @field_validator("benefits", "tradeoffs", "prerequisites", mode="before")
    @classmethod
    def normalize_bags(cls, value: object) -> tuple[str, ...]:
        return _normalize_string_bag(value, label="strategy bag")


class RuleProperties(EngineeringKnowledgeProperties):
    rule_kind: KnowledgeRuleKind = KnowledgeRuleKind.UNKNOWN
    rationale: str
    condition_expression: str | None = None
    recommendation_text: str | None = None
    default_severity: KnowledgeSeverity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("rationale", mode="before")
    @classmethod
    def normalize_rationale(cls, value: object) -> str:
        return require_nonblank(str(value), label="rationale")

    @field_validator("condition_expression", "recommendation_text", mode="before")
    @classmethod
    def normalize_optional_rule_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional rule field")


class ConstraintProperties(EngineeringKnowledgeProperties):
    constraint_kind: str
    rationale: str | None = None

    @field_validator("constraint_kind", mode="before")
    @classmethod
    def normalize_constraint_kind(cls, value: object) -> str:
        return require_nonblank(str(value), label="constraint_kind")

    @field_validator("rationale", mode="before")
    @classmethod
    def normalize_rationale(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="rationale")


class PlatformCapabilityProperties(EngineeringKnowledgeProperties):
    provider: str | None = None
    capability_category: str | None = None

    @field_validator("provider", "capability_category", mode="before")
    @classmethod
    def normalize_optional_capability_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional capability field")


class EngineeringKnowledgeCatalogMetadata(_KnowledgePropertyModel):
    """Release metadata for a curated knowledge catalog (not a graph node)."""

    catalog_id: str
    catalog_version: str
    name: str
    description: str | None = None
    published_at: datetime | None = None
    source: str | None = None

    @field_validator("catalog_id", "catalog_version", "name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="catalog field")

    @field_validator("description", "source", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional catalog field")

    @field_validator("source", mode="after")
    @classmethod
    def reject_credentialed_source(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _reject_credentialed_reference(value, label="source")

    @field_validator("published_at")
    @classmethod
    def require_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value


KnowledgePropertyModel = (
    EngineeringKnowledgeProperties
    | TechnologyProperties
    | FrameworkProperties
    | LanguageProperties
    | ArchitectureStyleProperties
    | PatternProperties
    | QualityAttributeProperties
    | EngineeringPracticeProperties
    | RiskTypeProperties
    | ModernizationStrategyProperties
    | RuleProperties
    | ConstraintProperties
    | PlatformCapabilityProperties
)


def properties_mapping(model: KnowledgePropertyModel) -> Mapping[str, Any]:
    return model.to_properties()
