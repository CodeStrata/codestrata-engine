"""CLI for release readiness (Phase 5.14)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.release import run_release_check

release_app = typer.Typer(
    name="release",
    help=(
        "Maintainer release readiness helpers.\n\n"
        "Validate package metadata, resources, CLI registration, schemas, "
        "prompts, defaults, deterministic providers, build artifacts, and "
        "clean-install smoke results."
    ),
    no_args_is_help=True,
)

DEFAULT_OUTPUT = Path("reports/release-readiness")


@release_app.command("check")
def release_check(
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory for release-readiness summary.json.",
        ),
    ] = DEFAULT_OUTPUT,
    dist: Annotated[
        Path,
        typer.Option("--dist", help="Directory containing wheel/sdist artifacts."),
    ] = Path("dist"),
    smoke_summary: Annotated[
        Path | None,
        typer.Option(
            "--smoke-summary",
            help="Path to clean-install smoke summary JSON.",
        ),
    ] = None,
    skip_smoke: Annotated[
        bool,
        typer.Option("--skip-smoke", help="Do not require clean-install smoke results."),
    ] = False,
    skip_build: Annotated[
        bool,
        typer.Option("--skip-build", help="Do not require dist/ wheel and sdist."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run CodeStrata release-readiness checks."""

    result = run_release_check(
        output_directory=output,
        dist_directory=dist,
        smoke_summary_path=smoke_summary or (output / "clean-install-smoke.json"),
        require_smoke=not skip_smoke,
        require_build_artifacts=not skip_build,
    )
    payload = result.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        typer.echo(f"release check: {status}")
        typer.echo(f"version: {result.codestrata_version}")
        typer.echo(f"summary: {result.summary_path}")
        for item in result.checks:
            mark = "PASS" if item.ok else "FAIL"
            typer.echo(f"  [{mark}] {item.name}: {item.detail}")
        if result.failure_reason:
            typer.echo(f"failure_reason: {result.failure_reason}")
    if not result.ok:
        raise typer.Exit(code=1)
