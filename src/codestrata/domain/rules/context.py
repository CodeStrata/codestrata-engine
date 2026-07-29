"""Typed execution context for Shared Rule Platform rules.

Rules consume this context only. They must not load files, query persistence,
or call network/AI services.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class LanguageInventoryView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    languages: tuple[str, ...] = ()

    @field_validator("languages", mode="before")
    @classmethod
    def normalize(cls, value: object) -> tuple[str, ...]:
        items = as_tuple(value)
        return tuple(sorted({str(item).strip().lower() for item in items if str(item).strip()}))


class DependencyFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    ecosystem: str | None = None
    version: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="dependency name")


class DependencyInventoryView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dependencies: tuple[DependencyFact, ...] = ()


class RepositoryFactView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_id: str
    repository_type: str | None = None
    display_name: str | None = None
    basenames: tuple[str, ...] = ()
    relative_paths: tuple[str, ...] = ()

    @field_validator("repository_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_id")

    @field_validator("basenames", "relative_paths", mode="before")
    @classmethod
    def normalize_paths(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))

    def has_basename(self, *candidates: str) -> bool:
        names = {item.lower() for item in self.basenames}
        return any(candidate.lower() in names for candidate in candidates)


class IncrementalChangeView(BaseModel):
    """Optional incremental change hints for planning (conservative by default)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    changed_paths: tuple[str, ...] = ()
    dependency_changed: bool = False
    build_changed: bool = False
    graph_changed: bool = False
    enterprise_context_changed: bool = False
    force_full_execution: bool = True


class RuleExecutionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fail_on_rule_error: bool = False
    max_matches_per_rule: int = Field(default=1000, ge=1, le=100_000)
    max_total_matches: int = Field(default=10_000, ge=1, le=1_000_000)
    max_evidence_per_match: int = Field(default=100, ge=1, le=10_000)
    max_rules_per_run: int = Field(default=1000, ge=1, le=100_000)
    claim_reuse: bool = False


class RuleExecutionContext(BaseModel):
    """Immutable typed inputs for shared rule evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    repository: RepositoryFactView
    languages: LanguageInventoryView = Field(default_factory=LanguageInventoryView)
    dependencies: DependencyInventoryView = Field(default_factory=DependencyInventoryView)
    snapshot_id: str | None = None
    assessment_run_id: str | None = None
    configuration_facts: dict[str, str] = Field(default_factory=dict)
    build_facts: dict[str, str] = Field(default_factory=dict)
    # Optional opaque typed views supplied by application layer (graphs, enterprise).
    repository_graph: Any | None = None
    engineering_knowledge_graph: Any | None = None
    assessment_graph: Any | None = None
    enterprise_context: Any | None = None
    # Optional Assessment Graph RuleContext for LegacyRuleAdapter (Phase 4.1.1).
    legacy_rule_context: Any | None = None
    # Optional ArchitectureAnalysisView for Architecture Intelligence (Phase 4.2).
    architecture_view: Any | None = None
    # Optional AggregatedComplexityEvidence for Technical Debt Intelligence (Phase 4.3.3).
    complexity_evidence: Any | None = None
    # Optional AggregatedDependencyEvidence for Dependency Intelligence (Phase 4.4.3).
    dependency_evidence: Any | None = None
    # Optional AggregatedRepositorySensitiveEvidence for Security Intelligence (Phase 4.5.3).
    repository_sensitive_evidence: Any | None = None
    # Optional AggregatedRepositoryTestingEvidence for Test Intelligence (Phase 4.6.3).
    repository_testing_evidence: Any | None = None
    # Optional AggregatedRepositoryCloudEvidence for Cloud Intelligence (Phase 4.7.3).
    repository_cloud_evidence: Any | None = None
    # Optional AggregatedRepositoryAiReadinessEvidence for AI Readiness (Phase 4.8.3).
    repository_ai_readiness_evidence: Any | None = None
    # Optional AggregatedRepositoryPerformanceEvidence for Performance (Phase 4.9.3).
    repository_performance_evidence: Any | None = None
    incremental: IncrementalChangeView = Field(default_factory=IncrementalChangeView)
    policy: RuleExecutionPolicy = Field(default_factory=RuleExecutionPolicy)
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("snapshot_id", "assessment_run_id", mode="before")
    @classmethod
    def normalize_optional_ids(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional context id")

    @field_validator("configuration_facts", "build_facts", "provenance", mode="before")
    @classmethod
    def normalize_maps(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("context maps must be dictionaries")
        return {
            require_nonblank(str(key), label="map key"): str(raw)
            for key, raw in sorted(value.items(), key=lambda item: str(item[0]))
        }

    @property
    def has_enterprise_context(self) -> bool:
        return self.enterprise_context is not None
