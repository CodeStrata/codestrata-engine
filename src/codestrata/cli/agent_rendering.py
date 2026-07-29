"""Rich terminal rendering for Agent Framework CLI results."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from codestrata.application.agents.models import (
    AgentStatus,
    AssessmentValidationWorkflowResult,
    ModernizationReviewResult,
    RepositoryAssessmentResult,
    RepositoryReviewResult,
    SnapshotReviewResult,
)
from codestrata.cli.agent_mapping import (
    agent_result_to_dict,
    dumps_agent_json,
    map_validation,
)

_console = Console(stderr=False)


def emit_result(
    result: object,
    *,
    as_json: bool,
) -> None:
    """Print JSON or a concise Rich summary for an agent workflow result."""

    payload = agent_result_to_dict(result)  # type: ignore[arg-type]
    if as_json:
        typer.echo(dumps_agent_json(payload), nl=False)
        return
    if isinstance(result, RepositoryReviewResult):
        _render_review(result, payload)
    elif isinstance(result, RepositoryAssessmentResult):
        _render_assessment(result, payload)
    elif isinstance(result, AssessmentValidationWorkflowResult):
        _render_validation(result, payload)
    elif isinstance(result, SnapshotReviewResult):
        _render_snapshot(result, payload)
    elif isinstance(result, ModernizationReviewResult):
        _render_modernization(result, payload)
    else:
        typer.echo(dumps_agent_json(payload), nl=False)


def _render_review(result: RepositoryReviewResult, payload: dict[str, Any]) -> None:
    repo = result.repository
    run = result.latest_run
    snap = result.latest_snapshot
    _header("Repository review", result.status)
    _kv("Workflow", result.workflow_id)
    if repo is not None:
        _kv("Repository", f"{repo.display_name} ({repo.repository_id})")
    if run is not None:
        _kv("Run", run.run_id)
    if snap is not None:
        _kv("Snapshot", snap.snapshot_id)
    _kv("AI status", result.ai_status)
    if result.finding_summary is not None:
        _kv("Findings", str(result.finding_summary.total))
        if result.finding_summary.by_severity:
            _kv("  by severity", _fmt_counts(result.finding_summary.by_severity))
        if result.finding_summary.by_category:
            _kv("  by category", _fmt_counts(result.finding_summary.by_category))
    if result.recommendation_summary is not None:
        _kv("Recommendations", str(result.recommendation_summary.total))
    _render_top_findings(result.top_findings)
    _render_top_recommendations(result.top_recommendations)
    _render_validation_block(payload.get("validation"))
    _render_warnings(result.warnings)
    _render_steps(result.steps)


def _render_assessment(
    result: RepositoryAssessmentResult,
    payload: dict[str, Any],
) -> None:
    _header("Repository assessment", result.status)
    _kv("Workflow", result.workflow_id)
    _kv("Repository ID", result.repository_id or "-")
    _kv("Snapshot ID", result.snapshot_id or "-")
    _kv("Run ID", result.run_id or "-")
    if result.prior_run_id:
        _kv("Previous run", result.prior_run_id)
    if result.prior_snapshot_id:
        _kv("Previous snapshot", result.prior_snapshot_id)
    if result.findings_count is not None:
        _kv("Findings", str(result.findings_count))
    if result.recommendations_count is not None:
        _kv("Recommendations", str(result.recommendations_count))
    _kv("AI status", result.ai_status)
    _render_validation_block(payload.get("validation"))
    _render_warnings(result.warnings)
    _render_steps(result.steps)


def _render_validation(
    result: AssessmentValidationWorkflowResult,
    payload: dict[str, Any],
) -> None:
    _header("Assessment validation", result.status)
    _kv("Workflow", result.workflow_id)
    _kv("Run", result.run_id)
    _kv("Repository", result.repository_id or "-")
    _kv("Snapshot", result.snapshot_id or "-")
    validation = payload.get("validation") or map_validation(result.validation)
    if validation is not None:
        _kv("Valid", str(validation["valid"]))
        _kv("Blocking", str(validation["blocking"]))
        _kv("Checked artifacts", str(len(validation.get("checked_artifacts") or [])))
        _kv("Checked findings", str(validation.get("checked_findings", 0)))
        _kv("Checked recommendations", str(validation.get("checked_recommendations", 0)))
        _kv("Checked components", str(validation.get("checked_components", 0)))
        _kv("AI validation", str(validation.get("ai_validation_status")))
        by_sev = validation.get("issues_by_severity") or {}
        if by_sev:
            _kv("Issues by severity", _fmt_counts(by_sev))
        issues = validation.get("issues") or []
        if issues:
            table = Table(title="Validation issues", show_header=True)
            table.add_column("Severity")
            table.add_column("Code")
            table.add_column("Message")
            for item in issues[:20]:
                table.add_row(
                    str(item.get("severity", "")),
                    str(item.get("code", "")),
                    str(item.get("message", ""))[:80],
                )
            _console.print(table)
            if validation.get("issue_truncated"):
                typer.echo(
                    f"  … {validation['issue_total_count'] - validation['issue_returned_count']}"
                    " more issues truncated"
                )
    _render_warnings(result.warnings)
    _render_steps(result.steps)


def _render_snapshot(result: SnapshotReviewResult, payload: dict[str, Any]) -> None:
    _header("Snapshot comparison", result.status)
    _kv("Workflow", result.workflow_id)
    comparison = payload.get("comparison")
    if comparison:
        _kv("Previous snapshot", comparison.get("previous_snapshot_id"))
        _kv("Current snapshot", comparison.get("current_snapshot_id"))
        counts = comparison.get("counts") or {}
        _kv(
            "Changes",
            (
                f"added={counts.get('added', 0)} "
                f"modified={counts.get('modified', 0)} "
                f"deleted={counts.get('deleted', 0)} "
                f"metadata={counts.get('metadata_changed', 0)} "
                f"renamed={counts.get('renamed', 0)}"
            ),
        )
        _kv("Rename detection", comparison.get("rename_detection", "not_supported"))
    _render_warnings(result.warnings)
    _render_steps(result.steps)


def _render_modernization(
    result: ModernizationReviewResult,
    payload: dict[str, Any],
) -> None:
    _header("Modernization review", result.status)
    _kv("Workflow", result.workflow_id)
    _kv("Repository", result.repository_id or "-")
    _kv("Run", result.run_id or "-")
    _kv("Snapshot", result.snapshot_id or "-")
    if result.risk_summary is not None:
        _kv("Risk findings", str(result.risk_summary.total))
    if result.recommendation_summary is not None:
        _kv("Recommendations", str(result.recommendation_summary.total))
    if result.roadmap_phases:
        _kv("Roadmap phases", ", ".join(result.roadmap_phases))
    if result.recommendation_groups:
        table = Table(title="Recommendation groups", show_header=True)
        table.add_column("Phase")
        table.add_column("Priority")
        table.add_column("Category")
        table.add_column("Count")
        for group in result.recommendation_groups[:20]:
            table.add_row(
                group.roadmap_phase or "-",
                group.priority or "-",
                group.category or "-",
                str(len(group.recommendation_ids)),
            )
        _console.print(table)
    if result.unresolved_recommendation_ids:
        _kv(
            "Unresolved refs",
            ", ".join(result.unresolved_recommendation_ids[:10]),
        )
    source = payload.get("source_distinction") or {}
    _kv(
        "Sources",
        f"deterministic={source.get('deterministic')} ai_enriched={source.get('ai_enriched')}",
    )
    _render_validation_block(payload.get("validation"))
    _render_warnings(result.warnings)
    _render_steps(result.steps)


def _header(title: str, status: AgentStatus) -> None:
    color = {
        AgentStatus.COMPLETED: typer.colors.GREEN,
        AgentStatus.BLOCKED: typer.colors.YELLOW,
        AgentStatus.FAILED: typer.colors.RED,
    }.get(status, typer.colors.WHITE)
    typer.secho(f"{title}: {status.value}", fg=color, bold=True)


def _kv(label: str, value: object) -> None:
    typer.echo(f"  {label}: {value}")


def _fmt_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _render_top_findings(findings: tuple[Any, ...]) -> None:
    if not findings:
        return
    table = Table(title="Top findings", show_header=True)
    table.add_column("Severity")
    table.add_column("Category")
    table.add_column("Title")
    for item in findings[:10]:
        table.add_row(item.severity, item.category, item.title[:60])
    _console.print(table)


def _render_top_recommendations(recommendations: tuple[Any, ...]) -> None:
    if not recommendations:
        return
    table = Table(title="Top recommendations", show_header=True)
    table.add_column("Priority")
    table.add_column("Category")
    table.add_column("Title")
    for item in recommendations[:10]:
        table.add_row(item.priority, item.category, item.title[:60])
    _console.print(table)


def _render_validation_block(validation: dict[str, Any] | None) -> None:
    if not validation:
        typer.echo("  Validation: (none)")
        return
    _kv(
        "Validation",
        f"valid={validation.get('valid')} blocking={validation.get('blocking')} "
        f"ai={validation.get('ai_validation_status')}",
    )
    by_sev = validation.get("issues_by_severity") or {}
    if by_sev:
        _kv("  issues", _fmt_counts(by_sev))


def _render_warnings(warnings: tuple[str, ...]) -> None:
    if not warnings:
        return
    typer.secho("  Warnings:", fg=typer.colors.YELLOW)
    for warning in warnings[:20]:
        typer.echo(f"    - {warning}")


def _render_steps(steps: tuple[Any, ...]) -> None:
    if not steps:
        return
    table = Table(title="Workflow steps", show_header=True)
    table.add_column("Step")
    table.add_column("Agent")
    table.add_column("Status")
    table.add_column("ms")
    for step in steps:
        duration = "-" if step.duration_ms is None else f"{step.duration_ms:.0f}"
        table.add_row(step.name, step.agent.value, step.status.value, duration)
    _console.print(table)
