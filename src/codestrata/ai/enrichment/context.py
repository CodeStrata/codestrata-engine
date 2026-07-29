"""Compact, deterministic AI enrichment context."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.recommendations import Recommendation, RecommendationResult
from codestrata.domain.repository_graph import RepositoryGraph, RepositoryNodeType
from codestrata.models import AnalysisResult
from codestrata.security.redaction import redact_secrets

AI_ENRICHMENT_CONTEXT_VERSION = "1.0.0"
DEFAULT_MAX_FINDINGS = 40
DEFAULT_MAX_RECOMMENDATIONS = 25
DEFAULT_MAX_DEPENDENCIES = 30
DEFAULT_MAX_TECHNOLOGIES = 20
DEFAULT_MAX_CONTEXT_CHARACTERS = 60_000
DEFAULT_MAX_SUMMARY_CHARS = 280
DEFAULT_MAX_EXCERPT_CHARS = 160


class AiEnrichmentBudgetError(ValueError):
    """Raised when enrichment context exceeds configured size budget."""


class RepositoryIdentitySummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_key: str
    display_name: str
    source_type: str | None = None
    file_count: int = Field(ge=0)

    @field_validator("repository_key", "display_name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository identity field")


class TechnologySummaryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    category: str | None = None
    version: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="technology name")


class DependencySummaryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ecosystem: str
    name: str
    namespace: str | None = None
    version: str | None = None
    scope: str | None = None

    @field_validator("ecosystem", "name", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="dependency field")


class FindingSummaryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    rule_id: str
    title: str
    severity: str
    category: str
    summary: str
    evidence_refs: tuple[str, ...] = ()

    @field_validator("id", "rule_id", "title", "severity", "category", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding summary field")

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def normalize_refs(cls, value: object) -> tuple[str, ...]:
        return as_tuple(value)


class RecommendationSummaryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    priority: str
    category: str
    summary: str
    related_finding_ids: tuple[str, ...] = ()
    action_titles: tuple[str, ...] = ()

    @field_validator("id", "title", "priority", "category", "summary", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="recommendation summary field")

    @field_validator("related_finding_ids", "action_titles", mode="before")
    @classmethod
    def normalize_seqs(cls, value: object) -> tuple[str, ...]:
        return as_tuple(value)


class AiEnrichmentContext(BaseModel):
    """Compact context sent to the model for enrichment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = AI_ENRICHMENT_CONTEXT_VERSION
    repository: RepositoryIdentitySummary
    technologies: tuple[TechnologySummaryItem, ...] = ()
    dependencies: tuple[DependencySummaryItem, ...] = ()
    findings: tuple[FindingSummaryItem, ...] = ()
    recommendations: tuple[RecommendationSummaryItem, ...] = ()
    truncated: bool = False
    truncation_notes: tuple[str, ...] = ()
    allowed_finding_ids: tuple[str, ...] = ()
    allowed_recommendation_ids: tuple[str, ...] = ()

    @field_validator(
        "technologies",
        "dependencies",
        "findings",
        "recommendations",
        "truncation_notes",
        "allowed_finding_ids",
        "allowed_recommendation_ids",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    def to_stable_json(self, *, indent: int = 2) -> str:
        payload = self.model_dump(mode="json")
        text = json.dumps(
            payload,
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        return redact_secrets(text)


class AiEnrichmentContextLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_findings: int = Field(default=DEFAULT_MAX_FINDINGS, ge=0)
    max_recommendations: int = Field(default=DEFAULT_MAX_RECOMMENDATIONS, ge=0)
    max_dependencies: int = Field(default=DEFAULT_MAX_DEPENDENCIES, ge=0)
    max_technologies: int = Field(default=DEFAULT_MAX_TECHNOLOGIES, ge=0)
    max_context_characters: int = Field(default=DEFAULT_MAX_CONTEXT_CHARACTERS, gt=0)
    max_summary_characters: int = Field(default=DEFAULT_MAX_SUMMARY_CHARS, gt=0)
    max_excerpt_characters: int = Field(default=DEFAULT_MAX_EXCERPT_CHARS, gt=0)


def build_ai_enrichment_context(
    *,
    analysis_result: AnalysisResult,
    rule_evaluation: RuleEvaluationResult,
    recommendation_result: RecommendationResult,
    repository_graph: RepositoryGraph | None = None,
    limits: AiEnrichmentContextLimits | None = None,
) -> AiEnrichmentContext:
    """Build a compact enrichment context with stable ordering and budgeting."""

    active_limits = limits or AiEnrichmentContextLimits()
    notes: list[str] = []
    truncated = False

    identity = analysis_result.repository
    repository = RepositoryIdentitySummary(
        repository_key=_safe_key(identity.name),
        display_name=identity.name,
        source_type=None,
        file_count=identity.total_files or len(identity.files),
    )

    technologies = _technology_summaries(
        analysis_result,
        limit=active_limits.max_technologies,
    )
    if len(analysis_result.technologies) > active_limits.max_technologies:
        truncated = True
        notes.append("technologies truncated")

    dependencies = _dependency_summaries(
        repository_graph,
        limit=active_limits.max_dependencies,
    )
    if repository_graph is not None:
        dep_count = sum(
            1
            for node in repository_graph.nodes
            if node.node_type == RepositoryNodeType.DEPENDENCY.value
        )
        if dep_count > active_limits.max_dependencies:
            truncated = True
            notes.append("dependencies truncated")

    ordered_findings = tuple(
        sorted(
            rule_evaluation.findings,
            key=lambda item: (item.severity.value, item.rule_id, item.id),
        )
    )
    selected_findings = ordered_findings[: active_limits.max_findings]
    if len(ordered_findings) > active_limits.max_findings:
        truncated = True
        notes.append("findings truncated")
    finding_items = tuple(_finding_summary(item, active_limits) for item in selected_findings)

    ordered_recs = tuple(
        sorted(
            recommendation_result.recommendations,
            key=lambda item: (item.priority.value, item.category.value, item.id),
        )
    )
    selected_recs = ordered_recs[: active_limits.max_recommendations]
    if len(ordered_recs) > active_limits.max_recommendations:
        truncated = True
        notes.append("recommendations truncated")
    recommendation_items = tuple(
        _recommendation_summary(item, active_limits) for item in selected_recs
    )

    context = AiEnrichmentContext(
        repository=repository,
        technologies=technologies,
        dependencies=dependencies,
        findings=finding_items,
        recommendations=recommendation_items,
        truncated=truncated,
        truncation_notes=tuple(notes),
        allowed_finding_ids=tuple(item.id for item in finding_items),
        allowed_recommendation_ids=tuple(item.id for item in recommendation_items),
    )
    serialized = context.to_stable_json()
    if len(serialized) > active_limits.max_context_characters:
        raise AiEnrichmentBudgetError(
            "AI enrichment context exceeds max_context_characters "
            f"({len(serialized)} > {active_limits.max_context_characters})"
        )
    _assert_no_absolute_paths(serialized)
    return context


def _technology_summaries(
    analysis_result: AnalysisResult,
    *,
    limit: int,
) -> tuple[TechnologySummaryItem, ...]:
    items: list[TechnologySummaryItem] = []
    for tech in sorted(analysis_result.technologies, key=lambda item: item.name.lower()):
        items.append(
            TechnologySummaryItem(
                name=tech.name,
                category=tech.category.value if tech.category is not None else None,
                version=tech.version,
            )
        )
        if len(items) >= limit:
            break
    return tuple(items)


def _dependency_summaries(
    repository_graph: RepositoryGraph | None,
    *,
    limit: int,
) -> tuple[DependencySummaryItem, ...]:
    if repository_graph is None:
        return ()
    items: list[DependencySummaryItem] = []
    nodes = [
        node
        for node in repository_graph.nodes
        if node.node_type == RepositoryNodeType.DEPENDENCY.value
    ]
    nodes.sort(
        key=lambda node: (
            str(node.properties.get("ecosystem") or ""),
            str(node.properties.get("namespace") or ""),
            str(node.properties.get("name") or ""),
        )
    )
    for node in nodes[:limit]:
        props = node.properties
        name = props.get("name")
        ecosystem = props.get("ecosystem")
        if not isinstance(name, str) or not isinstance(ecosystem, str):
            continue
        namespace = props.get("namespace")
        version = props.get("version")
        scope = props.get("scope")
        items.append(
            DependencySummaryItem(
                ecosystem=ecosystem,
                name=name,
                namespace=namespace if isinstance(namespace, str) else None,
                version=version if isinstance(version, str) else None,
                scope=scope if isinstance(scope, str) else None,
            )
        )
    return tuple(items)


def _finding_summary(
    finding: Finding,
    limits: AiEnrichmentContextLimits,
) -> FindingSummaryItem:
    refs: list[str] = []
    for evidence in finding.evidence[:3]:
        if evidence.path:
            refs.append(_clip(evidence.path, limits.max_excerpt_characters))
        elif evidence.excerpt:
            refs.append(_clip(evidence.excerpt, limits.max_excerpt_characters))
    return FindingSummaryItem(
        id=finding.id,
        rule_id=finding.rule_id,
        title=finding.title,
        severity=finding.severity.value,
        category=finding.category.value,
        summary=_clip(finding.description, limits.max_summary_characters),
        evidence_refs=tuple(refs),
    )


def _recommendation_summary(
    recommendation: Recommendation,
    limits: AiEnrichmentContextLimits,
) -> RecommendationSummaryItem:
    return RecommendationSummaryItem(
        id=recommendation.id,
        title=recommendation.title,
        priority=recommendation.priority.value,
        category=recommendation.category.value,
        summary=_clip(recommendation.summary, limits.max_summary_characters),
        related_finding_ids=recommendation.related_finding_ids,
        action_titles=tuple(action.title for action in recommendation.actions[:5]),
    )


def _clip(value: str, max_chars: int) -> str:
    compact = " ".join(require_nonblank(value, label="text").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _safe_key(name: str) -> str:
    compact = require_nonblank(name, label="repository name").strip().lower()
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in compact)
    return cleaned.strip("-") or "repository"


def _assert_no_absolute_paths(serialized: str) -> None:
    lowered = serialized.lower()
    for needle in ("/users/", "/home/", "c:\\", "file://"):
        if needle in lowered:
            raise AiEnrichmentBudgetError(
                "AI enrichment context must not include absolute filesystem paths"
            )


def optional_mapping(value: object) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value
    return None


def optional_string(value: object) -> str | None:
    if value is None:
        return None
    return optional_nonblank(str(value), label="optional string")
