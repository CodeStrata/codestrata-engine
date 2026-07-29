"""Mutable workflow context used during orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from codestrata.application.agents.evidence import AgentEvidence
from codestrata.application.agents.models import (
    AgentDecision,
    AgentStatus,
    AgentStep,
    WorkflowType,
)


@dataclass
class WorkflowContext:
    """In-progress workflow state shared across agent steps."""

    workflow_type: WorkflowType
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    repository_identifier: str | None = None
    repository_id: str | None = None
    snapshot_id: str | None = None
    run_id: str | None = None
    branch: str | None = None
    revision_id: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    current_step: str | None = None
    prior_run_id: str | None = None
    prior_snapshot_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    steps: list[AgentStep] = field(default_factory=list)
    evidence: list[AgentEvidence] = field(default_factory=list)
    decisions: list[AgentDecision] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    status: AgentStatus = AgentStatus.RUNNING

    def add_warning(self, message: str) -> None:
        compact = message.strip()
        if compact and compact not in self.warnings:
            self.warnings.append(compact)

    def add_evidence(self, *items: AgentEvidence) -> None:
        self.evidence.extend(items)

    def add_decision(self, decision: AgentDecision) -> None:
        self.decisions.append(decision)

    def add_step(self, step: AgentStep) -> None:
        self.steps.append(step)
        self.current_step = step.name

    def complete(self, status: AgentStatus) -> None:
        self.status = status
        self.completed_at = datetime.now(UTC)
