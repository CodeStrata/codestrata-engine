"""Human-readable rendering for incremental CLI commands."""

from __future__ import annotations

import typer

from codestrata.application.incremental.execution_record import IncrementalExecutionRecord
from codestrata.application.incremental.explainability import IncrementalExplanation
from codestrata.application.incremental.models import IncrementalAssessmentPlan
from codestrata.cli.incremental_mapping import dumps_json, plan_to_dict, record_to_dict


def emit_plan(plan: IncrementalAssessmentPlan, *, as_json: bool) -> None:
    if as_json:
        typer.echo(dumps_json(plan_to_dict(plan)))
        return
    typer.echo(f"Incremental plan: {plan.plan_id}")
    typer.echo(f"Mode: {plan.mode.value}")
    typer.echo(f"Full rebuild required: {plan.full_rebuild_required}")
    if plan.full_rebuild_reasons:
        typer.echo(f"Full rebuild reasons: {', '.join(plan.full_rebuild_reasons)}")
    change = plan.change_summary or {}
    typer.echo(
        "Changes: "
        f"added={change.get('added', 0)} "
        f"modified={change.get('modified', 0)} "
        f"deleted={change.get('deleted', 0)} "
        f"total={change.get('change_count', 0)}"
    )
    if plan.compatibility is not None:
        typer.echo(f"Compatible: {plan.compatibility.compatible}")
    impact = plan.impact_summary or {}
    typer.echo(
        "Impact: "
        f"files={impact.get('directly_changed_files', 0)} "
        f"findings={impact.get('impacted_findings', 0)} "
        f"recommendations={impact.get('impacted_recommendations', 0)}"
    )
    reuse = plan.reuse_summary or {}
    typer.echo(f"Reuse summary: {reuse.get('counts', reuse)}")
    typer.echo(f"Proposed steps: {len(plan.steps)}")
    for step in plan.steps[:20]:
        typer.echo(f"  {step.sequence}. {step.step_type.value}")
    if plan.warnings:
        typer.echo(f"Warnings: {', '.join(plan.warnings)}")


def emit_record(record: IncrementalExecutionRecord, *, as_json: bool) -> None:
    if as_json:
        typer.echo(dumps_json(record_to_dict(record)))
        return
    typer.echo(f"Execution: {record.execution_id}")
    typer.echo(f"Requested strategy: {record.requested_strategy}")
    typer.echo(f"Actual mode: {record.actual_mode.value}")
    typer.echo(f"Fallback used: {record.fallback_used}")
    if record.fallback_reasons:
        typer.echo(f"Fallback reasons: {', '.join(record.fallback_reasons)}")
    typer.echo(f"Run ID: {record.run_id}")
    typer.echo(f"Snapshot ID: {record.snapshot_id}")
    typer.echo(f"Trusted: {record.trusted}")
    if record.validation is not None:
        typer.echo(f"Validation: {record.validation.status.value}")
        if record.validation.blocking_issues:
            typer.echo(
                "Blocking issues: "
                + ", ".join(issue.code for issue in record.validation.blocking_issues[:10])
            )
        if record.validation.equivalent_to_full is not None:
            typer.echo(f"Equivalent to full: {record.validation.equivalent_to_full}")
    if record.metrics is not None:
        m = record.metrics
        typer.echo(
            "Changes: "
            f"added={m.added_files} modified={m.modified_files} "
            f"deleted={m.deleted_files} ratio={m.change_ratio}"
        )
        typer.echo(
            "Reuse: "
            f"files={m.files_reused}/{m.files_reused + m.files_rescanned} "
            f"findings={m.findings_reused}/{m.findings_reused + m.findings_regenerated} "
            f"recommendations={m.recommendations_reused}/"
            f"{m.recommendations_reused + m.recommendations_regenerated} "
            f"overall={m.overall_reuse_ratio}"
        )
    if record.warnings:
        typer.echo(f"Warnings: {', '.join(record.warnings[:20])}")


def emit_explanations(
    explanations: tuple[IncrementalExplanation, ...],
    *,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(dumps_json([item.model_dump(mode="json") for item in explanations]))
        return
    if not explanations:
        typer.echo("No explanations matched the filter.")
        return
    for item in explanations:
        subject = item.subject_id or item.subject_kind or "-"
        codes = ", ".join(item.reason_codes) if item.reason_codes else "-"
        typer.echo(f"[{item.kind.value}] {subject}: {item.summary} ({codes})")
