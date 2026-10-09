"""Comparison projection for architecture graph evidence and YAML outcomes.

Copies statuses, evidence subjects and declared language tiers. It does not
recompute cycles, fan-out, shares or centrality, and it does not claim that a
retained Python rule score matches the YAML result.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.structure.language_paths import (
    LanguageTierRecord,
    declared_language_tiers,
)
from codestrata.application.evidence.structure.normalize import StructuralGraphEvidence
from codestrata.application.rules.architecture.parity import (
    ARCHITECTURE_PARITY,
    NOT_RETAINED_ARCHITECTURE_RULES,
    PARITY_VERSION,
    NotRetainedRule,
    RuleParity,
    parity_by_yaml_id,
)
from codestrata.application.rules.execution.projections import (
    project_launch_html,
    project_launch_json,
    project_launch_sarif,
)
from codestrata.domain.rules.execution_models import LaunchExecutionBody

COMPARISON_SCHEMA = "codestrata.architecture.comparison.v1"


class OutcomeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    python_rule_id: str
    status: str
    coverage_state: str
    reason: str = ""
    evidence_subjects: tuple[str, ...] = ()


class GraphSnapshot(BaseModel):
    """Copied metric fields. Centrality stays descriptive."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_count: int
    cycle_complete: bool
    fan_out_status: str
    fan_out_serialized: str | None = None
    boundary_count: int
    boundary_status: str
    direction_count: int
    direction_status: str
    leakage_count: int
    leakage_status: str
    concentration_status: str
    concentration_serialized: str | None = None
    centrality_status: str = "descriptive"
    centrality: tuple[dict[str, str], ...] = ()


class ArchitectureComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = COMPARISON_SCHEMA
    schema_version: str = "1.0.0"
    parity_version: str = PARITY_VERSION
    score_equivalent: bool = False
    health_verdict: str = "none"
    old_score: None = None
    parity: tuple[RuleParity, ...]
    not_retained: tuple[NotRetainedRule, ...]
    records: tuple[OutcomeRecord, ...]
    graph: GraphSnapshot
    language_tiers: tuple[LanguageTierRecord, ...]
    launch_json: dict[str, object] = Field(default_factory=dict)
    launch_html: str = ""
    launch_sarif: dict[str, object] = Field(default_factory=dict)


def project_architecture_comparison(
    evidence: StructuralGraphEvidence,
    body: LaunchExecutionBody,
    *,
    language_tiers: tuple[LanguageTierRecord, ...] | None = None,
) -> ArchitectureComparison:
    mapping = parity_by_yaml_id()
    records: list[OutcomeRecord] = []
    for record in body.records:
        parity = mapping.get(record.rule_id)
        status = record.status.value if record.status is not None else record.coverage_state.value
        records.append(
            OutcomeRecord(
                rule_id=record.rule_id,
                python_rule_id=parity.python_rule_id if parity is not None else "",
                status=status,
                coverage_state=record.coverage_state.value,
                reason=record.reason or "",
                evidence_subjects=tuple(item.subject_id for item in record.evidence),
            )
        )
    centrality = tuple(
        {
            "node_id": item.node_id,
            "status": item.computation.status.value,
            "serialized": item.computation.serialized or "",
        }
        for item in evidence.centrality
    )
    graph = GraphSnapshot(
        cycle_count=evidence.cycles.count,
        cycle_complete=evidence.cycles.complete,
        fan_out_status=evidence.coupling.max_fan_out.status.value,
        fan_out_serialized=evidence.coupling.max_fan_out.serialized,
        boundary_count=evidence.boundary.count,
        boundary_status=evidence.boundary.computation.status.value,
        direction_count=evidence.direction.count,
        direction_status=evidence.direction.computation.status.value,
        leakage_count=evidence.leakage.count,
        leakage_status=evidence.leakage.computation.status.value,
        concentration_status=evidence.concentration.max_share.status.value,
        concentration_serialized=evidence.concentration.max_share.serialized,
        centrality=centrality,
    )
    return ArchitectureComparison(
        parity=ARCHITECTURE_PARITY,
        not_retained=NOT_RETAINED_ARCHITECTURE_RULES,
        records=tuple(records),
        graph=graph,
        language_tiers=language_tiers if language_tiers is not None else declared_language_tiers(),
        launch_json=project_launch_json(body),
        launch_html=project_launch_html(body),
        launch_sarif=project_launch_sarif(body),
    )


__all__ = [
    "COMPARISON_SCHEMA",
    "ArchitectureComparison",
    "GraphSnapshot",
    "OutcomeRecord",
    "project_architecture_comparison",
]
