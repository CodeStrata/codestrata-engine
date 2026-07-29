"""Assessment execution MCP tool."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from rich.console import Console

from codestrata.application.assessment import (
    DEFAULT_ASSESS_OUTPUT_DIRECTORY,
    AssessmentApplicationService,
)
from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import CodestrataSettings
from codestrata.interfaces.mcp.mapping import to_mcp_dict
from codestrata.interfaces.mcp.models import AssessmentExecutionResponse
from codestrata.interfaces.mcp.security import optional_filter, require_nonblank
from codestrata.interfaces.mcp.tools._common import run_bounded
from codestrata.reporting import AssessmentMode


def register_execution_tools(
    server: FastMCP,
    *,
    queries: KnowledgeQueryService,
    assessment_service: AssessmentApplicationService,
    settings: CodestrataSettings | None,
) -> None:
    @server.tool(name="run_assessment", structured_output=True)
    def run_assessment(
        repository: str,
        branch: str | None = None,
        with_ai: bool = False,
        config_path: str | None = None,
    ) -> dict[str, Any]:
        """Run a CodeStrata Engine assessment and persist knowledge artifacts.

        Scope: Community Engine (local). Optional AI when with_ai=true requires
        Engine AI provider credentials — not Platform API keys.

        Returns concise IDs and counts for follow-up query tools. Does not return
        HTML reports or full graphs.
        """

        def _run() -> dict[str, Any]:
            repo = require_nonblank(repository, label="repository")
            mode = (
                AssessmentMode.AI_ENHANCED if with_ai else AssessmentMode.DETERMINISTIC
            )
            resolved_config = (
                Path(require_nonblank(config_path, label="config_path"))
                if config_path is not None
                else Path("codestrata.toml")
            )
            quiet = Console(file=io.StringIO(), quiet=True)
            result = assessment_service.run(
                repo,
                Path(DEFAULT_ASSESS_OUTPUT_DIRECTORY),
                mode=mode,
                branch=optional_filter(branch, label="branch"),
                config_path=resolved_config,
                settings=settings,
                console=quiet,
                verbose=False,
            )

            ai_status = (
                "succeeded"
                if result.ai_executed
                else ("requested" if with_ai else "not_requested")
            )
            if with_ai and not result.ai_executed:
                ai_status = "failed_or_skipped"

            follow_ups: list[str] = []
            if result.knowledge_run_id:
                follow_ups.extend(
                    [
                        f"list_findings(run_id={result.knowledge_run_id})",
                        f"list_recommendations(run_id={result.knowledge_run_id})",
                        f"list_components(run_id={result.knowledge_run_id})",
                    ]
                )
            if result.knowledge_repository_id:
                follow_ups.append(
                    "get_latest_assessment("
                    f"repository_identifier={result.knowledge_repository_id})"
                )

            branch_value = optional_filter(branch, label="branch")
            revision_type = None
            revision_id = None
            if result.knowledge_run_id:
                summary = queries.get_assessment_run(result.knowledge_run_id)
                branch_value = summary.branch or branch_value
                revision_type = (
                    None
                    if summary.revision_type is None
                    else summary.revision_type.value
                )
                revision_id = summary.revision_id

            response = AssessmentExecutionResponse(
                run_id=result.knowledge_run_id,
                repository_id=result.knowledge_repository_id,
                snapshot_id=result.knowledge_snapshot_id,
                status="completed",
                repository_display_name=result.repository_name,
                branch=branch_value,
                revision_type=revision_type,
                revision_id=revision_id,
                findings_count=result.findings_count,
                recommendations_count=result.recommendations_count,
                phase3_findings_count=result.rule_finding_count,
                phase3_recommendations_count=result.phase3_recommendation_count,
                ai_requested=with_ai,
                ai_status=ai_status,
                report_generated=True,
                output_reference=str(result.run_directory),
                duration_ms=result.duration_ms,
                completed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                warnings=(),
                suggested_follow_ups=tuple(follow_ups),
            )
            return to_mcp_dict(response)

        return run_bounded("run_assessment", _run)
