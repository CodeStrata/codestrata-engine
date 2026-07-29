"""MCP tests for additive incremental tools (Phase 2F.3)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from codestrata.application.assessment import AssessmentApplicationService
from codestrata.application.incremental.errors import IncrementalRolloutDisabledError
from codestrata.application.incremental.execution_models import (
    IncrementalExecutionMode,
    IncrementalExecutionStatus,
)
from codestrata.application.incremental.execution_record import IncrementalExecutionRecord
from codestrata.application.incremental.explainability import IncrementalExplanationKind
from codestrata.application.incremental.inspection import IncrementalInspectionService
from codestrata.application.incremental.models import (
    IncrementalAssessmentPlan,
    IncrementalPlanMode,
)
from codestrata.application.incremental.operations import IncrementalOperationsService
from codestrata.application.incremental.provenance import InMemoryIncrementalExecutionRecordStore
from codestrata.application.incremental.rollout import (
    IncrementalRolloutMode,
    IncrementalRolloutPolicy,
)
from codestrata.application.incremental.service import IncrementalPlanningService
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.infrastructure.knowledge_store import SqliteKnowledgeStore
from codestrata.interfaces.mcp import create_mcp_server
from codestrata.interfaces.mcp.tools.incremental import register_incremental_tools
from codestrata.interfaces.mcp.tools.incremental_mapping import (
    map_incremental_error,
    map_plan,
)


def test_incremental_tools_registered_with_injection() -> None:
    store = InMemoryIncrementalExecutionRecordStore()
    now = datetime.now(UTC)
    store.save(
        IncrementalExecutionRecord(
            execution_id="exec-mcp-1",
            repository_id="repo-1",
            actual_mode=IncrementalExecutionMode.FULL_REBUILD_FALLBACK,
            status=IncrementalExecutionStatus.FALLBACK_COMPLETED,
            fallback_used=True,
            fallback_reasons=("test",),
            started_at=now,
            completed_at=now,
            explanations=(),
        )
    )
    operations = IncrementalOperationsService(
        planning_service=IncrementalPlanningService(),
        rollout=IncrementalRolloutPolicy(mode=IncrementalRolloutMode.PLAN_ONLY),
    )
    inspection = IncrementalInspectionService(store)
    server = FastMCP(name="test")
    register_incremental_tools(server, operations=operations, inspection=inspection)

    async def _check() -> None:
        tools = {tool.name for tool in await server.list_tools()}
        assert "create_incremental_assessment_plan" in tools
        assert "execute_incremental_assessment" in tools
        assert "get_incremental_execution" in tools
        assert "explain_incremental_execution" in tools

    asyncio.run(_check())


def test_default_composition_keeps_existing_tool_counts(tmp_path: Path) -> None:
    with SqliteKnowledgeStore(tmp_path / "knowledge") as store:
        server = create_mcp_server(
            query_service=KnowledgeQueryService(store),
            assessment_service=AssessmentApplicationService(),
            incremental_execution_service=IncrementalOperationsService(
                planning_service=IncrementalPlanningService(),
                rollout=IncrementalRolloutPolicy(mode=IncrementalRolloutMode.OFF),
            ),
            incremental_inspection_service=IncrementalInspectionService(
                InMemoryIncrementalExecutionRecordStore()
            ),
        )

        async def _check() -> None:
            tools = [tool.name for tool in await server.list_tools()]
            agent_tools = [name for name in tools if name.endswith("_with_agents")]
            incremental = [name for name in tools if "incremental" in name]
            assert len(agent_tools) == 5
            assert len(incremental) == 4
            assert len(tools) >= 29

        asyncio.run(_check())


def test_rollout_disabled_error_mapping() -> None:
    payload = map_incremental_error(
        IncrementalRolloutDisabledError(
            "disabled",
            reason_code="rollout_off",
        )
    )
    assert payload["error"] is True
    assert payload["reason_code"] == "rollout_off"


def test_map_plan_stable() -> None:
    plan = IncrementalAssessmentPlan(
        plan_id=str(uuid4()),
        mode=IncrementalPlanMode.FULL_REBUILD,
        full_rebuild_required=True,
        full_rebuild_reasons=("no_previous_run",),
        created_at=datetime.now(UTC),
    )
    payload = map_plan(plan)
    assert payload["mode"] == "full_rebuild"
    assert "plan_id" in payload


def test_explanation_kind_values_stable() -> None:
    assert IncrementalExplanationKind.FALLBACK.value == "fallback"
