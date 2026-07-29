"""Thin Typer adapter for incremental assessment (Phase 2F.3).

Commands call IncrementalOperationsService / IncrementalInspectionService only.
They do not reimplement planning, execution, or validation logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.incremental.errors import (
    IncrementalPlanningError,
)
from codestrata.application.incremental.execution_models import IncrementalExecutionRequest
from codestrata.application.incremental.explainability import (
    ExplanationFilters,
    IncrementalExplanationKind,
)
from codestrata.application.incremental.models import IncrementalPlanningRequest
from codestrata.cli.incremental_mapping import (
    EXIT_ERROR,
    exit_code_for_error,
    exit_code_for_record,
)
from codestrata.cli.incremental_rendering import emit_explanations, emit_plan, emit_record
from codestrata.config import CodestrataSettings, load_settings

incremental_app = typer.Typer(
    name="incremental",
    help=(
        "Incremental assessment (explicit opt-in; advanced).\n\n"
        "Requires [incremental].rollout_mode=plan_only|opt_in. "
        "`codestrata assess` remains a full rebuild regardless of rollout mode."
    ),
    no_args_is_help=True,
)


def _load_settings_or_exit(config: Path) -> CodestrataSettings:
    try:
        return load_settings(config)
    except (FileNotFoundError, ValueError, OSError) as error:
        typer.secho(f"Configuration error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ERROR) from error


def _compose_operations(settings: CodestrataSettings, config: Path) -> object:
    from codestrata.application.assessment import AssessmentApplicationService
    from codestrata.application.incremental.factory import (
        AssessmentApplicationServiceRunner,
        create_incremental_operations_service,
    )
    from codestrata.infrastructure.knowledge_store import create_knowledge_query_service

    queries = create_knowledge_query_service(settings=settings)
    runner = AssessmentApplicationServiceRunner(
        AssessmentApplicationService(),
        config_path=config,
    )
    return create_incremental_operations_service(
        assessment_runner=runner,
        query_service=queries,
        settings=settings,
    )


def _compose_inspection(settings: CodestrataSettings) -> object:
    from codestrata.application.incremental.inspection import IncrementalInspectionService
    from codestrata.application.incremental.provenance import (
        FileIncrementalExecutionRecordStore,
    )

    store = FileIncrementalExecutionRecordStore(
        Path(settings.knowledge.directory) / "incremental_executions"
    )
    return IncrementalInspectionService(store)


@incremental_app.command("plan")
def plan_command(
    repository: Annotated[
        str,
        typer.Argument(help="Repository path, key, or configured repository."),
    ],
    previous_run_id: Annotated[
        str | None,
        typer.Option("--previous-run-id", help="Base assessment run ID."),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch hint for previous-run resolution."),
    ] = None,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON."),
    ] = False,
) -> None:
    """Create and display an IncrementalAssessmentPlan (no assessment execution)."""

    settings = _load_settings_or_exit(config)
    try:
        operations = _compose_operations(settings, config)
        plan = operations.create_plan(  # type: ignore[attr-defined]
            IncrementalPlanningRequest(
                repository_identifier=repository,
                previous_run_id=previous_run_id,
                branch=branch,
            )
        )
    except IncrementalPlanningError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=exit_code_for_error(error)) from error
    except Exception as error:  # noqa: BLE001 — CLI boundary
        typer.secho(f"Incremental plan failed: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ERROR) from error
    emit_plan(plan, as_json=as_json)


@incremental_app.command("assess")
def assess_command(
    repository: Annotated[
        str,
        typer.Argument(help="Repository path, key, or configured repository."),
    ],
    previous_run_id: Annotated[
        str | None,
        typer.Option("--previous-run-id", help="Base assessment run ID."),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch hint for previous-run resolution."),
    ] = None,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Report output directory."),
    ] = Path("reports"),
    with_ai: Annotated[
        bool,
        typer.Option("--with-ai", help="Run AI enrichment on the assessment path."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON."),
    ] = False,
    equivalence_check: Annotated[
        bool,
        typer.Option(
            "--equivalence-check",
            help="Enable semantic equivalence check when a full reference is available.",
        ),
    ] = False,
) -> None:
    """Explicitly request incremental execution with mandatory full fallback."""

    settings = _load_settings_or_exit(config)
    try:
        operations = _compose_operations(settings, config)
        record = operations.execute(  # type: ignore[attr-defined]
            IncrementalExecutionRequest(
                repository=repository,
                output_directory=str(output),
                branch=branch,
                previous_run_id=previous_run_id,
                with_ai=with_ai,
                config_path=str(config),
            ),
            enable_equivalence_check=equivalence_check or None,
        )
    except Exception as error:  # noqa: BLE001 — CLI boundary
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=exit_code_for_error(error)) from error
    emit_record(record, as_json=as_json)
    raise typer.Exit(code=exit_code_for_record(record))


@incremental_app.command("explain")
def explain_command(
    execution_id: Annotated[
        str,
        typer.Argument(help="Persisted incremental execution ID."),
    ],
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON."),
    ] = False,
    kind: Annotated[
        str | None,
        typer.Option("--kind", help="Filter by explanation kind."),
    ] = None,
    subject_id: Annotated[
        str | None,
        typer.Option("--subject-id", help="Filter by subject ID."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum explanations to display."),
    ] = 100,
) -> None:
    """Explain a persisted incremental execution."""

    settings = _load_settings_or_exit(config)
    try:
        inspection = _compose_inspection(settings)
        kind_enum = IncrementalExplanationKind(kind) if kind else None
        explanations = inspection.explain_execution(  # type: ignore[attr-defined]
            execution_id,
            filters=ExplanationFilters(
                kind=kind_enum,
                subject_id=subject_id,
                limit=limit,
            ),
        )
        record = inspection.get_execution(execution_id)  # type: ignore[attr-defined]
    except Exception as error:  # noqa: BLE001 — CLI boundary
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=exit_code_for_error(error)) from error
    if not as_json:
        typer.echo(f"Execution: {record.execution_id}")
        typer.echo(f"Mode: {record.actual_mode.value}")
        typer.echo(f"Fallback: {record.fallback_used}")
        if record.validation is not None:
            typer.echo(f"Validation: {record.validation.status.value}")
    emit_explanations(explanations, as_json=as_json)
