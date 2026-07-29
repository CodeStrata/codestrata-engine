"""Assessment agent: execute assessments via AssessmentApplicationService."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codestrata.application.agents.errors import AgentDependencyError, AgentExecutionError
from codestrata.application.agents.models import RepositoryAssessmentRequest
from codestrata.application.assessment.service import (
    DEFAULT_ASSESS_OUTPUT_DIRECTORY,
    AssessmentApplicationService,
    AssessmentCommandError,
    AssessmentCommandResult,
)
from codestrata.reporting.modernization_models import AssessmentMode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssessmentAgentResult:
    """Concise assessment outcome suitable for ValidationAgent."""

    command: AssessmentCommandResult
    repository_id: str | None
    snapshot_id: str | None
    run_id: str | None
    warnings: tuple[str, ...] = ()
    ai_requested: bool = False


@dataclass
class AssessmentAgent:
    """Coordinate assessment execution through AssessmentApplicationService.

    Does not scan repositories, build graphs, execute rules, call Bedrock,
    persist artifacts, or invoke CLI/MCP adapters.
    """

    assessment_service: AssessmentApplicationService
    settings: object | None = None
    default_output_directory: Path = field(default_factory=lambda: DEFAULT_ASSESS_OUTPUT_DIRECTORY)

    def __post_init__(self) -> None:
        if self.assessment_service is None:
            raise AgentDependencyError("AssessmentApplicationService is required")

    def run_assessment(
        self,
        request: RepositoryAssessmentRequest,
        *,
        provider: Any | None = None,
        scanner: Any | None = None,
        knowledge_store: Any | None = None,
    ) -> AssessmentAgentResult:
        mode = AssessmentMode.AI_ENHANCED if request.with_ai else AssessmentMode.DETERMINISTIC
        output = (
            Path(request.output_directory)
            if request.output_directory
            else self.default_output_directory
        )
        config_path = Path(request.config_path) if request.config_path else Path("codestrata.toml")

        logger.info(
            "assessment.run_start",
            extra={
                "repository_identifier": request.repository,
                "branch": request.branch,
                "with_ai": request.with_ai,
            },
        )

        try:
            command = self.assessment_service.run(
                request.repository,
                output,
                mode=mode,
                branch=request.branch,
                config_path=config_path,
                settings=self.settings,  # type: ignore[arg-type]
                provider=provider,
                scanner=scanner,
                knowledge_store=knowledge_store,
            )
        except AssessmentCommandError as error:
            raise AgentExecutionError(str(error)) from error
        except Exception as error:
            raise AgentExecutionError(
                f"Assessment execution failed: {type(error).__name__}"
            ) from error

        warnings: list[str] = []
        repository_id = command.knowledge_repository_id
        snapshot_id = command.knowledge_snapshot_id
        run_id = command.knowledge_run_id
        if repository_id is None or snapshot_id is None or run_id is None:
            warnings.append(
                "Assessment completed without complete knowledge-store IDs "
                f"(repository_id={repository_id!r}, snapshot_id={snapshot_id!r}, "
                f"run_id={run_id!r})"
            )

        logger.info(
            "assessment.run_complete",
            extra={
                "repository_id": repository_id,
                "snapshot_id": snapshot_id,
                "run_id": run_id,
                "status": "completed",
            },
        )
        return AssessmentAgentResult(
            command=command,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            run_id=run_id,
            warnings=tuple(warnings),
            ai_requested=request.with_ai,
        )
