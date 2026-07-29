"""Immutable Phase 3 finding models produced by the Rule Engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.findings.enums import FindingCategory, FindingSeverity, FindingSource
from codestrata.domain.findings.ids import build_finding_id
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank


class FindingEvidence(BaseModel):
    """Explainable evidence supporting a graph-rule finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_type: str
    source_id: str
    path: str | None = None
    excerpt: str | None = None
    node_id: NodeId | None = None

    @field_validator("evidence_type", "source_id", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding evidence field")

    @field_validator("path", "excerpt", mode="before")
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        return optional_nonblank(str(value), label="optional finding evidence field")


class Finding(BaseModel):
    """One deterministic Assessment-Graph rule finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    rule_id: str
    title: str
    description: str
    severity: FindingSeverity
    category: FindingCategory
    source: FindingSource = FindingSource.RULE
    evidence: tuple[FindingEvidence, ...] = ()
    affected_assessment_node_ids: tuple[NodeId, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "rule_id", "title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="finding field")

    @field_validator("evidence", "affected_assessment_node_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        return dict(value)

    @classmethod
    def create(
        cls,
        *,
        rule_id: str,
        title: str,
        description: str,
        severity: FindingSeverity,
        category: FindingCategory,
        evidence: Sequence[FindingEvidence] = (),
        affected_assessment_node_ids: Sequence[NodeId] = (),
        metadata: Mapping[str, Any] | None = None,
        subject_keys: Sequence[str] = (),
    ) -> Finding:
        """Construct a finding with a deterministic identity."""

        node_ids = tuple(affected_assessment_node_ids)
        subjects = tuple(subject_keys) or tuple(node.root for node in node_ids)
        return cls(
            id=build_finding_id(rule_id=rule_id, subject_keys=subjects),
            rule_id=rule_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            source=FindingSource.RULE,
            evidence=tuple(evidence),
            affected_assessment_node_ids=node_ids,
            metadata=dict(metadata or {}),
        )


class RuleEvaluationResult(BaseModel):
    """Aggregated deterministic output of one Rule Engine execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[Finding, ...] = ()
    rules_evaluated: tuple[str, ...] = ()
    rules_skipped: tuple[str, ...] = ()
    finding_count: int = Field(ge=0)

    @field_validator("findings", "rules_evaluated", "rules_skipped", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @classmethod
    def from_findings(
        cls,
        *,
        findings: Sequence[Finding],
        rules_evaluated: Sequence[str],
        rules_skipped: Sequence[str] = (),
    ) -> RuleEvaluationResult:
        ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
        evaluated = tuple(
            sorted({require_nonblank(item, label="rule_id") for item in rules_evaluated})
        )
        skipped = tuple(sorted({require_nonblank(item, label="rule_id") for item in rules_skipped}))
        return cls(
            findings=ordered,
            rules_evaluated=evaluated,
            rules_skipped=skipped,
            finding_count=len(ordered),
        )
