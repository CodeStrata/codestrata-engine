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
        "  codestrata report validate .codestrata-artifacts/assessments/<repo>/current/assessment.json\n"
        "  codestrata open\n"
        "  codestrata report open --path .codestrata-artifacts/assessments/<repo>/current/assessment.html\n\n"
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
            help=(
                "assessment (default, inferred from current Assessment) or eir "
                "(portfolio Engineering Intelligence)."
            ),
        ),
    ] = None,
    repository_id: Annotated[
        str | None,
        typer.Option(
            "--repository-id",
            help="Logical repository id (default: latest current assessment folder).",
        ),
    ] = None,
    portfolio_id: Annotated[
        str | None,
        typer.Option(
            "--portfolio-id",
            help="Logical portfolio id for EIR publish (default: release-validation).",
        ),
    ] = None,
    artifacts_root: Annotated[
        Path,
        typer.Option("--artifacts-root", help="Local .codestrata-artifacts root."),
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
    """Publish the local CURRENT Assessment Report to a branded public URL.

    Interactive (recommended)::

        codestrata report publish

    Non-interactive / CI::

        codestrata report publish --confirm-public-publish
        codestrata report publish --confirm-public-publish --acknowledge-private-repository

    Publishing is an explicit public action and is separate from telemetry consent.
    Local reports always remain available. Publishing never runs automatically after assess.
    """

    from codestrata.community_cloud.report_publishing import (
        PRIVATE_REPO_WARNING,
        PUBLIC_PUBLISH_WARNING,
        ReportPublishError,
        publish_local_assessment,
        publish_local_eir,
        user_facing_publish_error,
    )

    interactive = (
        os.environ.get("CODESTRATA_FORCE_INTERACTIVE", "").strip().lower()
        in {"1", "true", "yes", "on"}
    ) or (
        not is_machine_mode() and sys.stdin.isatty() and sys.stdout.isatty()
    )
    kind = (report_type or "").strip().lower() or None

    # Infer assessment vs EIR when --type omitted.
    if kind is None:
        assess_hits = sorted(
            (artifacts_root / "assessments").glob("*/current/assessment.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ) if (artifacts_root / "assessments").is_dir() else []
        eir_hits = sorted(
            (artifacts_root / "intelligence").glob(
                "*/current/engineering-intelligence-report.html"
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ) if (artifacts_root / "intelligence").is_dir() else []
        if assess_hits and eir_hits:
            error(
                "Both Assessment and EIR current reports exist. "
                "Pass --type assessment or --type eir."
            )
            raise typer.Exit(code=2)
        if eir_hits and not assess_hits:
            kind = "eir"
        else:
            kind = "assessment"

    confirmed = confirm
    private_ack = acknowledge_private
    logical_id = ""
    local_html = ""

    try:
        if kind in {"assessment", "assess"}:
            root = artifacts_root / "assessments"
            if repository_id:
                current = root / repository_id / "current"
                rid = repository_id
            else:
                currents = sorted(
                    root.glob("*/current/assessment.html"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if not currents:
                    raise ReportPublishError(
                        "No current report found. Run `codestrata assess --repo .` first."
                    )
                current = currents[0].parent
                rid = currents[0].parent.parent.name
            logical_id = rid
            local_html = str(current / "assessment.html")
            is_private = rid.startswith("local-")

            if interactive and not confirmed:
                typer.echo(PUBLIC_PUBLISH_WARNING)
                if is_private:
                    typer.echo(PRIVATE_REPO_WARNING)
                if not typer.confirm("Publish report?", default=False):
                    info("Publish cancelled. Local report remains unchanged.")
                    raise typer.Exit(code=0)
                confirmed = True
                private_ack = True if is_private else private_ack
            else:
                if not confirmed:
                    error(
                        "Non-interactive publish requires --confirm-public-publish. "
                        "Local report remains unchanged."
                    )
                    tip("Interactive: codestrata report publish")
                    raise typer.Exit(code=2)
                if is_private and not private_ack:
                    error(PRIVATE_REPO_WARNING)
                    tip(
                        "Re-run with --confirm-public-publish "
                        "--acknowledge-private-repository"
                    )
                    raise typer.Exit(code=2)

            result = publish_local_assessment(
                current_dir=current,
                logical_repository_id=rid,
                private_repository_acknowledged=private_ack or not is_private,
                confirm_public_publish=True,
            )
        elif kind in {"eir", "intelligence", "engineering_intelligence"}:
            pid = (portfolio_id or "release-validation").strip()
            logical_id = pid
            current = artifacts_root / "intelligence" / pid / "current"
            local_html = str(current / "engineering-intelligence-report.html")
            if interactive and not confirmed:
                typer.echo(
                    "This will publish your current Engineering Intelligence Report. "
                    "Anyone with the resulting link can view it."
                )
                if not typer.confirm("Publish report?", default=False):
                    info("Publish cancelled. Local report remains unchanged.")
                    raise typer.Exit(code=0)
                confirmed = True
            elif not confirmed:
                error(
                    "Non-interactive publish requires --confirm-public-publish. "
                    "Local report remains unchanged."
                )
                raise typer.Exit(code=2)
            result = publish_local_eir(
                current_dir=current,
                portfolio_id=pid,
                confirm_public_publish=True,
            )
        else:
            error("Unsupported --type. Use assessment or eir.")
            raise typer.Exit(code=2)
    except ReportPublishError as exc:
        error(user_facing_publish_error(exc))
        raise typer.Exit(code=1) from exc
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 - failure isolation
        error(user_facing_publish_error(exc))
        raise typer.Exit(code=1) from exc

    label = (
        "Assessment Report published."
        if kind in {"assessment", "assess"}
        else "Engineering Intelligence Report published."
    )
    success(label)
    typer.echo("")
    typer.echo("Public URL:")
    typer.echo(result.public_url)
    typer.echo("")
    if result.local_html_path or local_html:
        typer.echo("Local report:")
        typer.echo(result.local_html_path or local_html)
        typer.echo("")
    tip("Anyone with the public link can view the published report.")
    tip(
        "Cloud keeps current + previous only; older public URLs for the same "
        "repository/portfolio return 404 after replacement."
    )

    try:
        from codestrata.community_cloud.public_report_url_manifest import (
            record_published_url,
        )

        report_kind = (
            "assessment"
            if kind in {"assessment", "assess"}
            else "engineering_intelligence"
        )
        record_published_url(
            report_type=report_kind,  # type: ignore[arg-type]
            logical_id=str(logical_id).strip(),
            public_url=result.public_url,
            source_slice=os.environ.get("CODESTRATA_VALIDATION_SLICE"),
        )
    except Exception:  # noqa: BLE001 — never fail publish on evidence write
        pass


__all__ = [
    "open_html_report",
    "register_open_command",
    "report_app",
]
