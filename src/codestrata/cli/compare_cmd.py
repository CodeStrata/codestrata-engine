"""Explicit baseline/candidate comparison. No hidden baseline selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from codestrata.cli.community_contract import EXIT_FAILURE, EXIT_USAGE, MIGRATION_MESSAGES
from codestrata.models import AnalysisResult
from codestrata.reporting.assessment_canonical import canonical_html_for_analysis
from codestrata.services.scan_comparison_service import ScanComparisonService


def _load_report(path: Path) -> AnalysisResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    payload.pop("comparison", None)
    return AnalysisResult.model_validate(payload)


def register_compare_command(app: typer.Typer) -> None:
    """Register ``codestrata compare``."""

    @app.command("compare", rich_help_panel="Primary")
    def compare_command(
        baseline: Annotated[
            Path,
            typer.Option(
                "--baseline",
                help="Explicit prior report.json. Required; nothing is selected for you.",
            ),
        ],
        candidate: Annotated[
            Path,
            typer.Option(
                "--candidate",
                help="Explicit candidate report.json. Required.",
            ),
        ],
    ) -> None:
        """Compare two explicit assessment reports.

        Both paths are required. A missing file or omitted flag is usage
        error 2. Incompatible or unreadable reports exit 1. There is no
        hidden baseline and no login.
        """

        typer.echo(MIGRATION_MESSAGES["compare"])
        for label, path in (("baseline", baseline), ("candidate", candidate)):
            if not path.is_file():
                typer.echo(f"{label} report not found: {path}", err=True)
                raise typer.Exit(code=EXIT_USAGE)
        try:
            baseline_result = _load_report(baseline)
            candidate_result = _load_report(candidate)
            comparison = ScanComparisonService().compare_results(
                current=candidate_result,
                baseline=baseline_result,
                current_timestamp=candidate.name,
                baseline_timestamp=baseline.name,
                evaluate_lifecycle=True,
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            ValidationError,
        ) as error:
            typer.echo(f"compare failed: {error}", err=True)
            raise typer.Exit(code=EXIT_FAILURE) from error

        canonical_html = canonical_html_for_analysis(
            candidate_result.model_copy(update={"comparison": comparison})
        )
        report_path = candidate.with_name("comparison-canonical-report.html")
        report_path.write_text(canonical_html, encoding="utf-8")
        summary: dict[str, Any] = {
            "baseline": str(baseline),
            "candidate": str(candidate),
            "baseline_available": comparison.baseline_available,
            "hidden_baseline": False,
            "canonical_html_path": str(report_path),
            "resolved_findings": len(comparison.resolved_findings),
            "compatibility_status": comparison.compatibility_status,
            "overall_movement": comparison.summary.overall_movement,
            "canonical_html": canonical_html,
        }
        typer.echo(json.dumps(summary, indent=2))
