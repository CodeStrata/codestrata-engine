"""Deterministic agent planning (no LLM planner in this increment)."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from codestrata.application.agents.models import WorkflowType


class AgentPlanStep(BaseModel):
    """One explicit bounded plan step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    agent: str
    description: str


class AgentPlan(BaseModel):
    """Explicit workflow plan returned by a planner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_type: WorkflowType
    steps: tuple[AgentPlanStep, ...] = ()


class AgentPlanner(Protocol):
    """Extension point for future optional planners."""

    def plan(self, workflow_type: WorkflowType) -> AgentPlan:
        """Return an explicit bounded plan for a workflow."""


class DeterministicAgentPlanner:
    """Hard-coded plans for supported workflows."""

    def plan(self, workflow_type: WorkflowType) -> AgentPlan:
        steps = _PLANS.get(workflow_type, ())
        return AgentPlan(workflow_type=workflow_type, steps=steps)


_PLANS: dict[WorkflowType, tuple[AgentPlanStep, ...]] = {
    WorkflowType.REPOSITORY_REVIEW: (
        AgentPlanStep(
            name="resolve_repository_context",
            agent="knowledge",
            description="Resolve repository and latest assessment context",
        ),
        AgentPlanStep(
            name="retrieve_review_artifacts",
            agent="knowledge",
            description="Load findings, recommendations, components, and AI status",
        ),
        AgentPlanStep(
            name="validate_assessment",
            agent="validation",
            description="Validate persisted assessment completeness",
        ),
        AgentPlanStep(
            name="assemble_review",
            agent="orchestrator",
            description="Assemble grounded repository review package",
        ),
    ),
    WorkflowType.REPOSITORY_ASSESSMENT: (
        AgentPlanStep(
            name="resolve_repository_context",
            agent="knowledge",
            description="Resolve prior repository context when available",
        ),
        AgentPlanStep(
            name="retrieve_previous_assessment",
            agent="knowledge",
            description="Capture previous completed assessment IDs",
        ),
        AgentPlanStep(
            name="run_assessment",
            agent="assessment",
            description="Execute AssessmentApplicationService",
        ),
        AgentPlanStep(
            name="retrieve_new_assessment",
            agent="knowledge",
            description="Load newly persisted assessment",
        ),
        AgentPlanStep(
            name="validate_assessment",
            agent="validation",
            description="Validate persisted run and artifacts",
        ),
        AgentPlanStep(
            name="assemble_result",
            agent="orchestrator",
            description="Assemble assessment workflow result",
        ),
    ),
    WorkflowType.SNAPSHOT_REVIEW: (
        AgentPlanStep(
            name="compare_snapshots",
            agent="knowledge",
            description="Compare persisted manifests",
        ),
        AgentPlanStep(
            name="assemble_result",
            agent="orchestrator",
            description="Assemble snapshot review result",
        ),
    ),
    WorkflowType.ASSESSMENT_VALIDATION: (
        AgentPlanStep(
            name="validate_assessment",
            agent="validation",
            description="Validate a persisted assessment run",
        ),
        AgentPlanStep(
            name="assemble_result",
            agent="orchestrator",
            description="Assemble validation workflow result",
        ),
    ),
    WorkflowType.MODERNIZATION_REVIEW: (
        AgentPlanStep(
            name="resolve_repository_context",
            agent="knowledge",
            description="Resolve repository and assessment for modernization review",
        ),
        AgentPlanStep(
            name="retrieve_recommendations",
            agent="knowledge",
            description="Load persisted recommendations and findings",
        ),
        AgentPlanStep(
            name="validate_assessment",
            agent="validation",
            description="Validate assessment grounding",
        ),
        AgentPlanStep(
            name="assemble_modernization_review",
            agent="orchestrator",
            description="Assemble modernization review package",
        ),
    ),
}


def plan_step_count(workflow_type: WorkflowType) -> int:
    return len(_PLANS.get(workflow_type, ()))
