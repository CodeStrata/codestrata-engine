"""CLI for MVP acceptance harness (Phase 5.13)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.acceptance import (
    load_acceptance_summary,
    run_mvp_acceptance,
)
from codestrata.application.acceptance.targets import ACCEPTANCE_TARGETS, ROOT

acceptance_app = typer.Typer(
    name="acceptance",
    help=(
        "Maintainer acceptance harness.\n\n"
        "Runs live onboard → report validate → grounded questions → MCP health → "
        "determinism for dogfood repositories."
    ),
    no_args_is_help=True,
)

DEFAULT_OUTPUT = Path("reports/mvp-acceptance")


@acceptance_app.command("run")
def acceptance_run(
    repository: Annotated[
        list[str] | None,
        typer.Option(
            "--repository",
            "-r",
            help=(
                "Repository id to include (repeatable). "
                "Defaults to codestrata, spring-petclinic, synthetic-multilang."
            ),
        ),
    ] = None,
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Path to codestrata.toml."),
    ] = Path("codestrata.toml"),
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory for acceptance summaries and per-repo artifacts.",
        ),
    ] = DEFAULT_OUTPUT,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run the live MVP acceptance harness."""

    selected = tuple(repository) if repository else None
    if selected:
        known = {label for label, _ in ACCEPTANCE_TARGETS}
        unknown = [name for name in selected if name not in known]
        if unknown:
            typer.echo(
                "Unknown repository id(s): "
                + ", ".join(unknown)
                + ". Known: "
                + ", ".join(sorted(known)),
                err=True,
            )
            raise typer.Exit(code=2)

    result = run_mvp_acceptance(
        output_directory=output,
        config_path=config,
        repositories=selected,
    )
    payload = result.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        typer.echo(f"mvp acceptance: {status}")
        typer.echo(f"output: {output}")
        typer.echo(f"elapsed_ms: {result.elapsed_ms:.1f}")
        for repo in result.repositories:
            mark = "PASS" if repo.ok else ("SKIP" if repo.skipped else "FAIL")
            typer.echo(
                f"  [{mark}] {repo.repository}: onboard={repo.onboarding_status} "
                f"findings={repo.findings} recs={repo.recommendations} "
                f"roadmap={repo.roadmap_initiatives} chunks={repo.chunks} "
                f"validate={repo.report_validation} qa={repo.question_answer} "
                f"mcp={repo.mcp_health} determinism={repo.determinism} "
                f"({repo.elapsed_ms:.0f} ms)"
            )
            if repo.failure_reason:
                typer.echo(f"         reason: {repo.failure_reason}")
        if result.failure_reason:
            typer.echo(f"failure_reason: {result.failure_reason}")
    if not result.ok:
        raise typer.Exit(code=1)


@acceptance_app.command("status")
def acceptance_status(
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory containing summary.json from a prior acceptance run.",
        ),
    ] = DEFAULT_OUTPUT,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show the latest MVP acceptance summary."""

    summary = load_acceptance_summary(output)
    if summary is None:
        typer.echo(f"No acceptance summary found at {output / 'summary.json'}", err=True)
        typer.echo(
            "Known targets: " + ", ".join(f"{label}={path}" for label, path in ACCEPTANCE_TARGETS),
            err=True,
        )
        typer.echo(f"workspace root: {ROOT}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(summary, indent=2, sort_keys=True))
        return

    ok = bool(summary.get("ok"))
    typer.echo(f"mvp acceptance status: {'PASS' if ok else 'FAIL'}")
    typer.echo(f"elapsed_ms: {summary.get('elapsed_ms')}")
    if summary.get("failure_reason"):
        typer.echo(f"failure_reason: {summary['failure_reason']}")
    for repo in summary.get("repositories") or []:
        mark = "PASS" if repo.get("ok") else ("SKIP" if repo.get("skipped") else "FAIL")
        typer.echo(
            f"  [{mark}] {repo.get('repository')}: "
            f"onboard={repo.get('onboarding_status')} "
            f"findings={repo.get('findings')} "
            f"recs={repo.get('recommendations')} "
            f"roadmap={repo.get('roadmap_initiatives')} "
            f"chunks={repo.get('chunks')} "
            f"validate={repo.get('report_validation')} "
            f"qa={repo.get('question_answer')} "
            f"mcp={repo.get('mcp_health')} "
            f"determinism={repo.get('determinism')}"
        )
    if not ok:
        raise typer.Exit(code=1)
