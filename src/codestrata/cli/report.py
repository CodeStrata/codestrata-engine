"""CLI for report contract validation and opening HTML reports."""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from codestrata.application.report_validation import (
    validate_report_json,
    validation_result_payload,
)
from codestrata.cli.ux import (
    DOCS_TROUBLESHOOTING,
    error,
    format_actionable_error,
    format_path_link,
    info,
    is_machine_mode,
    success,
    tip,
)

report_app = typer.Typer(
    name="report",
    help=(
        "Report helpers for assess HTML/JSON outputs.\n\n"
        "Examples:\n"
        "  codestrata report validate "
        ".codestrata-artifacts/assessments/<repo>/current/assessment.json\n"
        "  codestrata open\n"
        "  codestrata report open --path "
        ".codestrata-artifacts/assessments/<repo>/current/assessment.html\n\n"
        "Validate assessment.json schema/references where applicable, "
        "and open the customer HTML report.\n\n"
        f"Troubleshooting: {DOCS_TROUBLESHOOTING}"
    ),
    no_args_is_help=True,
)


def _find_latest_html_report(search_root: Path) -> Path | None:
    """Locate current/assessment.html preferentially, else newest HTML report."""

    if not search_root.is_dir():
        return None
    # Slice 17.15: prefer logical current slots.
    current_hits = sorted(
        search_root.glob("*/current/assessment.html"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if current_hits:
        return current_hits[0]
    modern = list(search_root.rglob("assessment.html"))
    legacy = list(search_root.rglob("report.html"))
    candidates = [path for path in modern + legacy if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def open_html_report(
    *,
    path: Path | None = None,
    output: Path = Path(".codestrata-artifacts/assessments"),
    no_browser: bool = False,
) -> Path:
    """Resolve and optionally open an HTML assessment report."""

    target = path.expanduser() if path is not None else _find_latest_html_report(output)
    if target is None:
        raise FileNotFoundError(
            format_actionable_error(
                what="No HTML report found.",
                why=f"Looked under {_display(output)} for assessment.html (or report.html).",
                fix=(
                    "Run: codestrata assess --repo . --no-ai\n"
                    "  Or pass: codestrata open --path <path-to-assessment.html>"
                ),
            )
        )
    if not target.is_file():
        raise FileNotFoundError(
            format_actionable_error(
                what=f"HTML report not found: {_display(target)}",
                why="The path does not exist or is not a file.",
                fix="Pass a valid assessment.html from a completed assess run.",
            )
        )
    if not no_browser and not is_machine_mode():
        webbrowser.open(target.resolve().as_uri())
    return target.resolve()


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except (OSError, ValueError):
        return str(path)


@report_app.command("validate")
def validate_report(
    report: Annotated[
        Path,
        typer.Argument(help="Path to report.json from an assess/onboard run."),
    ],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validate a CodeStrata report.json against the hardened report contract."""

    result = validate_report_json(report)
    payload = validation_result_payload(result)
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        typer.echo(f"report validation: {status}")
        typer.echo(f"schema_version: {result.schema_version}")
        typer.echo(
            f"issues: {payload['issue_count']} "
            f"(errors={payload['error_count']}, warnings={payload['warning_count']})"
        )
        for item in result.issues:
            typer.echo(f"  [{item.severity}] {item.code} @ {item.path}: {item.message}")
    if not result.ok:
        raise typer.Exit(code=1)


@report_app.command("open")
def report_open_command(
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            help="Explicit path to assessment.html (default: latest under --output).",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Assessments directory used to find the latest HTML report.",
        ),
    ] = Path(".codestrata-artifacts/assessments"),
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="Print the report path without opening a browser.",
        ),
    ] = False,
) -> None:
    """Open the latest (or specified) HTML Engineering Assessment report."""

    try:
        target = open_html_report(path=path, output=output, no_browser=no_browser)
    except FileNotFoundError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc

    try:
        from codestrata.telemetry.service import get_telemetry_service

        get_telemetry_service().record_report_opened()
    except Exception:  # noqa: BLE001 - never break open
        pass

    if is_machine_mode() or no_browser or os.environ.get("CI"):
        typer.echo(str(target))
        return
    success("Report opened.")
    info(f"HTML Report: {format_path_link(target)}")
    tip("Re-open later with: codestrata open")


def register_open_command(app: typer.Typer) -> None:
    """Register top-level ``codestrata open`` (primary report experience)."""

    @app.command("open", rich_help_panel="Primary")
    def open_command(
        path: Annotated[
            Path | None,
            typer.Option(
                "--path",
                help="Explicit path to assessment.html (default: latest under --output).",
            ),
        ] = None,
        output: Annotated[
            Path,
            typer.Option(
                "--output",
                "-o",
                help="Assessments directory used to find the latest HTML report.",
            ),
        ] = Path(".codestrata-artifacts/assessments"),
        no_browser: Annotated[
            bool,
            typer.Option(
                "--no-browser",
                help="Print the report path without opening a browser.",
            ),
        ] = False,
    ) -> None:
        """Open the latest Engineering Assessment HTML report in your browser.

        Examples:

            codestrata open
            codestrata open --path reports/<run>/report.html
            codestrata open --no-browser
        """

        report_open_command(path=path, output=output, no_browser=no_browser)


@report_app.command("publish")
def report_publish_command(
    report_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            help="Deprecated. Hosted assessment/EIR publish is removed from Community.",
        ),
    ] = None,
    repository_id: Annotated[
        str | None,
        typer.Option("--repository-id", help="Deprecated. Not used."),
    ] = None,
    portfolio_id: Annotated[
        str | None,
        typer.Option("--portfolio-id", help="Deprecated. Portfolio publish is removed."),
    ] = None,
    artifacts_root: Annotated[
        Path,
        typer.Option("--artifacts-root", help="Local .codestrata-artifacts root (unused)."),
    ] = Path(".codestrata-artifacts"),
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm-public-publish",
            help=(
                "Required in non-interactive/CI mode. Interactive terminals prompt "
                "instead (default answer: No)."
            ),
        ),
    ] = False,
    acknowledge_private: Annotated[
        bool,
        typer.Option(
            "--acknowledge-private-repository",
            help=(
                "Required in non-interactive/CI mode for local-/private repository "
                "assessments. Interactive terminals include this in the confirmation."
            ),
        ),
    ] = False,
) -> None:
    """Deprecated: Community Engine does not upload reports.

    Interactive confirmation still runs (``Publish report?``); hosted upload is refused.

    Interactive::

        codestrata report publish

    Non-interactive / CI::

        codestrata report publish --confirm-public-publish
    """

    from codestrata.community_cloud.report_publishing import PUBLIC_PUBLISH_WARNING
    from codestrata.integration.community_runtime import COMMUNITY_CLOUD_PUBLISH_REMOVED

    _ = (report_type, repository_id, portfolio_id, artifacts_root, acknowledge_private)
    interactive = (
        os.environ.get("CODESTRATA_FORCE_INTERACTIVE", "").strip().lower()
        in {"1", "true", "yes", "on"}
    ) or (not is_machine_mode() and sys.stdin.isatty() and sys.stdout.isatty())
    if interactive and not confirm:
        typer.echo(PUBLIC_PUBLISH_WARNING)
        if not typer.confirm("Publish report?", default=False):
            info("Publish cancelled. Local report remains unchanged.")
            raise typer.Exit(code=0)
    elif not confirm:
        error(
            "Non-interactive publish requires --confirm-public-publish. "
            "Local report remains unchanged."
        )
        tip("Interactive: codestrata report publish")
        raise typer.Exit(code=2)
    error(COMMUNITY_CLOUD_PUBLISH_REMOVED)
    tip("Open a local report with: codestrata open")
    raise typer.Exit(code=2)


__all__ = [
    "open_html_report",
    "register_open_command",
    "report_app",
]
