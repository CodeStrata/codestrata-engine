"""Additive MCP tools for incremental assessment (Phase 2F.3)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from codestrata.application.incremental.errors import IncrementalRolloutDisabledError
from codestrata.application.incremental.execution_models import IncrementalExecutionRequest
from codestrata.application.incremental.explainability import (
    ExplanationFilters,
    IncrementalExplanationKind,
)
from codestrata.application.incremental.inspection import IncrementalInspectionService
from codestrata.application.incremental.models import IncrementalPlanningRequest
from codestrata.application.incremental.operations import IncrementalOperationsService
from codestrata.interfaces.mcp.tools._common import require_nonblank, run_bounded
from codestrata.interfaces.mcp.tools.incremental_mapping import (
    map_execution_record,
    map_explanations,
    map_plan,
)


def register_incremental_tools(
    server: FastMCP,
    *,
    operations: IncrementalOperationsService | None,
    inspection: IncrementalInspectionService | None,
) -> None:
    """Register four additive incremental tools (no changes to existing tools)."""

    @server.tool(name="create_incremental_assessment_plan", structured_output=True)
    def create_incremental_assessment_plan(
        repository_identifier: str,
        previous_run_id: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Create an IncrementalAssessmentPlan without executing assessment."""

        def _run() -> dict[str, Any]:
            if operations is None:
                raise IncrementalRolloutDisabledError(
                    "Incremental operations service is not configured",
                    reason_code="operations_missing",
                )
            plan = operations.create_plan(
                IncrementalPlanningRequest(
                    repository_identifier=require_nonblank(
                        repository_identifier, label="repository_identifier"
                    ),
                    previous_run_id=previous_run_id,
                    branch=branch,
                )
            )
            return map_plan(plan)

        return run_bounded("create_incremental_assessment_plan", _run)

    @server.tool(name="execute_incremental_assessment", structured_output=True)
    def execute_incremental_assessment(
        repository_identifier: str,
        output_directory: str = "reports",
        previous_run_id: str | None = None,
        branch: str | None = None,
        with_ai: bool = False,
        equivalence_check: bool = False,
    ) -> dict[str, Any]:
        """Explicit opt-in incremental execution with mandatory full fallback."""

        def _run() -> dict[str, Any]:
            if operations is None:
                raise IncrementalRolloutDisabledError(
                    "Incremental operations service is not configured",
                    reason_code="operations_missing",
                )
            record = operations.execute(
                IncrementalExecutionRequest(
                    repository=require_nonblank(
                        repository_identifier, label="repository_identifier"
                    ),
                    output_directory=require_nonblank(output_directory, label="output_directory"),
                    previous_run_id=previous_run_id,
                    branch=branch,
                    with_ai=with_ai,
                ),
                enable_equivalence_check=equivalence_check or None,
            )
            return map_execution_record(record)

        return run_bounded("execute_incremental_assessment", _run)

    @server.tool(name="get_incremental_execution", structured_output=True)
    def get_incremental_execution(execution_id: str) -> dict[str, Any]:
        """Retrieve a persisted IncrementalExecutionRecord."""

        def _run() -> dict[str, Any]:
            if inspection is None:
                raise IncrementalRolloutDisabledError(
                    "Incremental inspection service is not configured",
                    reason_code="inspection_missing",
                )
            record = inspection.get_execution(require_nonblank(execution_id, label="execution_id"))
            return map_execution_record(record)

        return run_bounded("get_incremental_execution", _run)

    @server.tool(name="explain_incremental_execution", structured_output=True)
    def explain_incremental_execution(
        execution_id: str,
        kind: str | None = None,
        subject_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return bounded deterministic explanations for an execution."""

        def _run() -> dict[str, Any]:
            if inspection is None:
                raise IncrementalRolloutDisabledError(
                    "Incremental inspection service is not configured",
                    reason_code="inspection_missing",
                )
            kind_enum = IncrementalExplanationKind(kind) if kind else None
            explanations = inspection.explain_execution(
                require_nonblank(execution_id, label="execution_id"),
                filters=ExplanationFilters(
                    kind=kind_enum,
                    subject_id=subject_id,
                    limit=max(1, min(limit, 10_000)),
                ),
            )
            return {"explanations": map_explanations(explanations)}

        return run_bounded("explain_incremental_execution", _run)
