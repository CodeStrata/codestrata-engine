"""Thin Typer adapter for Agent Framework workflows.

Commands call :class:`AgentOrchestrator` only. They do not invoke MCP, nest
``codestrata assess``, or reimplement workflow logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.agents import (
    AgentConfigurationError,
    AgentDependencyError,
    AgentError,
    AgentEvidenceError,
    AgentExecutionError,
    AgentStatus,
    AgentStepError,
    AgentValidationError,
    AgentWorkflowBlockedError,
    AssessmentValidationRequest,
    ModernizationReviewRequest,
    RepositoryAssessmentRequest,
    RepositoryReviewRequest,
    SnapshotReviewRequest,
    create_agent_orchestrator,
    resolve_agent_policy,
)
from codestrata.cli.agent_mapping import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_SUCCESS,
    exit_code_for_status,
)
from codestrata.cli.agent_rendering import emit_result
from codestrata.config import CodestrataSettings, load_settings

agent_app = typer.Typer(
    name="agent",
    help=(
        "CodeStrata Agent Framework workflows.\n\n"
        "Higher-level orchestration over application services "
        "(review, assess+validate, compare, modernization-review).\n"
        "Prefer `codestrata assess` for the direct assessment application-service path."
    ),
    no_args_is_help=True,
)


def _load_settings_or_exit(config: Path) -> CodestrataSettings:
    try:
        return load_settings(config)
    except (FileNotFoundError, ValueError, OSError) as error:
        typer.secho(f"Configuration error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ERROR) from error


def _compose(
    settings: CodestrataSettings,
    *,
    max_findings: int | None = None,
    max_recommendations: int | None = None,
    max_components: int | None = None,
    dependency_depth: int | None = None,
    include_assessment: bool = True,
) -> tuple[object, object]:
    """Return (orchestrator, query_service)."""

    try:
        if not settings.agents.enabled:
            typer.secho(
                "Agent Framework is disabled ([agents].enabled=false).",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=EXIT_ERROR)
        policy = resolve_agent_policy(
            settings,
            max_findings=max_findings,
            max_recommendations=max_recommendations,
            max_components=max_components,
            dependency_depth=dependency_depth,
        )
        from codestrata.infrastructure.knowledge_store import create_knowledge_query_service

        queries = create_knowledge_query_service(settings=settings)
        orchestrator = create_agent_orchestrator(
            query_service=queries,
            settings=settings,
            policy=policy,
            include_assessment_agent=include_assessment,
        )
        return orchestrator, queries
    except AgentConfigurationError as error:
        typer.secho(f"Agent configuration error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ERROR) from error
    except AgentDependencyError as error:
        typer.secho(f"Agent dependency error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ERROR) from error


def _orchestrator_or_exit(
    settings: CodestrataSettings,
    *,
    max_findings: int | None = None,
    max_recommendations: int | None = None,
    max_components: int | None = None,
    dependency_depth: int | None = None,
    include_assessment: bool = True,
) -> object:
    orchestrator, _queries = _compose(
        settings,
        max_findings=max_findings,
        max_recommendations=max_recommendations,
        max_components=max_components,
        dependency_depth=dependency_depth,
        include_assessment=include_assessment,
    )
    return orchestrator


def _handle_agent_error(error: BaseException) -> None:
    if isinstance(
        error,
        (
            AgentConfigurationError,
            AgentDependencyError,
            AgentExecutionError,
            AgentStepError,
            AgentValidationError,
            AgentEvidenceError,
            AgentWorkflowBlockedError,
            AgentError,
        ),
    ):
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ERROR) from error
    typer.secho(
        f"Unexpected agent failure: {type(error).__name__}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code=EXIT_ERROR) from error


def _finish(result: object, *, as_json: bool) -> None:
    emit_result(result, as_json=as_json)
    status = getattr(result, "status", AgentStatus.FAILED)
    validation = getattr(result, "validation", None)
    blocking = bool(getattr(validation, "blocking", False)) if validation else False
    code = exit_code_for_status(status, validation_blocking=blocking)
    if code != EXIT_SUCCESS:
        raise typer.Exit(code=code)


@agent_app.command("review")
def review(
    repository: Annotated[
        str,
        typer.Option("--repository", help="Repository ID, canonical key, or GitHub URL."),
    ],
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Optional branch filter for latest assessment."),
    ] = None,
    max_findings: Annotated[
        int | None,
        typer.Option("--max-findings", help="Max findings to assemble (1-500)."),
    ] = None,
    max_recommendations: Annotated[
        int | None,
        typer.Option("--max-recommendations", help="Max recommendations (1-500)."),
    ] = None,
    max_components: Annotated[
        int | None,
        typer.Option("--max-components", help="Max components (1-1000)."),
    ] = None,
    dependency_depth: Annotated[
        int | None,
        typer.Option("--dependency-depth", help="Dependency traversal depth (1-3)."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit structured JSON instead of terminal summary."),
    ] = False,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
) -> None:
    """Review persisted repository knowledge through AgentOrchestrator."""

    settings = _load_settings_or_exit(config)
    orchestrator = _orchestrator_or_exit(
        settings,
        max_findings=max_findings,
        max_recommendations=max_recommendations,
        max_components=max_components,
        dependency_depth=dependency_depth,
        include_assessment=False,
    )
    try:
        result = orchestrator.review_repository(  # type: ignore[attr-defined]
            RepositoryReviewRequest(
                repository_identifier=repository.strip(),
                branch=branch,
            )
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        _handle_agent_error(error)
    _finish(result, as_json=as_json)


@agent_app.command("assess")
def assess(
    repository: Annotated[
        str,
        typer.Option("--repository", help="Local path or GitHub URL to assess."),
    ],
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Optional branch for clone/assess."),
    ] = None,
    with_ai: Annotated[
        bool,
        typer.Option("--with-ai", help="Enable optional AI enrichment."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit structured JSON instead of terminal summary."),
    ] = False,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
) -> None:
    """Run assessment + validation through AgentOrchestrator.

    Unlike ``codestrata assess``, this workflow also retrieves prior context, loads
    persisted IDs, validates the run, and returns structured workflow steps.
    """

    settings = _load_settings_or_exit(config)
    orchestrator = _orchestrator_or_exit(settings, include_assessment=True)
    try:
        result = orchestrator.assess_repository(  # type: ignore[attr-defined]
            RepositoryAssessmentRequest(
                repository=repository.strip(),
                branch=branch,
                with_ai=with_ai,
                config_path=str(config),
            )
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        _handle_agent_error(error)
    _finish(result, as_json=as_json)


@agent_app.command("validate")
def validate(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Persisted assessment run ID."),
    ],
    repository: Annotated[
        str | None,
        typer.Option(
            "--repository",
            help="Optional repository ID to verify run ownership.",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit structured JSON instead of terminal summary."),
    ] = False,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
) -> None:
    """Validate a persisted assessment through AgentOrchestrator."""

    settings = _load_settings_or_exit(config)
    orchestrator, queries = _compose(settings, include_assessment=False)
    repository_id = None
    if repository is not None and repository.strip():
        try:
            repository_id = queries.resolve_repository(repository.strip()).repository_id  # type: ignore[attr-defined]
        except Exception as error:  # noqa: BLE001
            typer.secho(f"Unable to resolve repository: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=EXIT_ERROR) from error

    try:
        result = orchestrator.validate_assessment(  # type: ignore[attr-defined]
            AssessmentValidationRequest(
                run_id=run_id.strip(),
                repository_id=repository_id,
            )
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        _handle_agent_error(error)
    _finish(result, as_json=as_json)


@agent_app.command("compare")
def compare(
    previous_snapshot: Annotated[
        str,
        typer.Option("--previous-snapshot", help="Previous snapshot ID."),
    ],
    current_snapshot: Annotated[
        str,
        typer.Option("--current-snapshot", help="Current snapshot ID."),
    ],
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit structured JSON instead of terminal summary."),
    ] = False,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
) -> None:
    """Compare two persisted snapshots through AgentOrchestrator."""

    settings = _load_settings_or_exit(config)
    orchestrator = _orchestrator_or_exit(settings, include_assessment=False)
    try:
        result = orchestrator.compare_repository_snapshots(  # type: ignore[attr-defined]
            SnapshotReviewRequest(
                previous_snapshot_id=previous_snapshot.strip(),
                current_snapshot_id=current_snapshot.strip(),
            )
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        _handle_agent_error(error)
    _finish(result, as_json=as_json)


@agent_app.command("modernization-review")
def modernization_review(
    repository: Annotated[
        str,
        typer.Option("--repository", help="Repository ID, canonical key, or GitHub URL."),
    ],
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", help="Optional specific assessment run ID."),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Optional branch filter (reserved)."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit structured JSON instead of terminal summary."),
    ] = False,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
) -> None:
    """Assemble a grounded modernization review from persisted recommendations."""

    del branch  # reserved for future filter parity with review
    settings = _load_settings_or_exit(config)
    orchestrator = _orchestrator_or_exit(settings, include_assessment=False)
    try:
        result = orchestrator.modernization_review(  # type: ignore[attr-defined]
            ModernizationReviewRequest(
                repository_identifier=repository.strip(),
                run_id=None if run_id is None else run_id.strip(),
            )
        )
    except Exception as error:  # noqa: BLE001 - CLI boundary
        _handle_agent_error(error)
    _finish(result, as_json=as_json)


__all__ = [
    "EXIT_BLOCKED",
    "EXIT_ERROR",
    "EXIT_SUCCESS",
    "agent_app",
    "assess",
    "compare",
    "modernization_review",
    "review",
    "validate",
]
