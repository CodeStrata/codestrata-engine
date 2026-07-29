"""Shared agent evidence records."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceSourceKind(StrEnum):
    """Kinds of durable sources that may ground agent conclusions."""

    REPOSITORY = "repository"
    ASSESSMENT_RUN = "assessment_run"
    SNAPSHOT = "snapshot"
    SNAPSHOT_COMPARISON = "snapshot_comparison"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    FINDING_EXPLANATION = "finding_explanation"
    RECOMMENDATION_EXPLANATION = "recommendation_explanation"
    COMPONENT = "component"
    DEPENDENCY = "dependency"
    AI_EXECUTION = "ai_execution"
    AI_ENRICHMENT = "ai_enrichment"
    ARTIFACT = "artifact"


class AgentEvidence(BaseModel):
    """One grounded evidence item assembled from application DTOs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    evidence_type: str
    source_id: str
    source_kind: EvidenceSourceKind
    title: str
    summary: str
    related_ids: tuple[str, ...] = ()
    deterministic: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence_id", "evidence_type", "source_id", "title", "summary", mode="before")
    @classmethod
    def require_nonblank(cls, value: object) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("must be a nonempty string")
        return text


def evidence_id_for(source_kind: EvidenceSourceKind, source_id: str) -> str:
    return f"evidence:{source_kind.value}:{source_id}"


def dedupe_evidence(items: list[AgentEvidence]) -> tuple[AgentEvidence, ...]:
    seen: set[str] = set()
    ordered: list[AgentEvidence] = []

    def sort_key(value: AgentEvidence) -> tuple[str, str, str]:
        return (value.source_kind.value, value.source_id, value.evidence_id)

    for item in sorted(items, key=sort_key):
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        ordered.append(item)
    return tuple(ordered)
