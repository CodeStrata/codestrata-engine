"""Thin CLI adapters for Shared Rule Platform (list / inspect / explain)."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from codestrata.application.rules.architecture.pack import ArchitectureRulePack
from codestrata.application.rules.errors import RuleApplicationError
from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.cli.rules_mapping import map_explanation, map_rule_view
from codestrata.cli.rules_rendering import render_rule_detail, render_rules_table
from codestrata.domain.rules.enums import RuleCategory

rules_app = typer.Typer(
    name="rules",
    help=(
        "Inspect registered engineering rules used during assess.\n\n"
        "Lists and inspects registered production rules. The Architecture pack is "
        "discoverable here; assess merge requires "
        "`[rules] enabled` and `[rules.architecture] enabled`. "
        "CLI rename to codestrata is deferred to a future rebranding milestone."
    ),
    no_args_is_help=True,
)


def _parse_category(value: str | None) -> RuleCategory | None:
    if value is None or not value.strip():
        return None
    compact = value.strip().lower()
    try:
        return RuleCategory(compact)
    except ValueError as error:
        raise typer.BadParameter(
            f"Unknown category '{value}'. Use architecture, technical_debt, "
            "security, performance, platform, or experimental."
        ) from error


@rules_app.command("list")
def list_rules(
    category: Annotated[
        str | None,
        typer.Option("--category", help="Filter by rule category (e.g. architecture)."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON."),
    ] = False,
) -> None:
    """List registered production shared rules."""

    service = create_rule_analysis_service()
    views = service.list_rules(
        category=_parse_category(category),
        include_non_production=False,
    )
    rows = [map_rule_view(view) for view in views]
    if json_output:
        payload: dict[str, object] = {"rules": rows}
        if category and category.strip().lower() == "architecture":
            payload["pack"] = ArchitectureRulePack().to_dict()
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    render_rules_table(rows)


@rules_app.command("inspect")
def inspect_rule(
    rule_id: Annotated[str, typer.Argument(help="Stable rule ID.")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON."),
    ] = False,
) -> None:
    """Inspect one production shared rule."""

    service = create_rule_analysis_service()
    try:
        view = service.inspect_rule(rule_id)
    except RuleApplicationError as error:
        typer.echo(error.safe_message, err=True)
        raise typer.Exit(code=1) from error
    if not view.production:
        typer.echo("Rule not found", err=True)
        raise typer.Exit(code=1)
    row = map_rule_view(view)
    if json_output:
        typer.echo(json.dumps(row, indent=2, ensure_ascii=False))
        return
    render_rule_detail(row)


@rules_app.command("explain")
def explain_rule(
    rule_id: Annotated[str, typer.Argument(help="Stable rule ID.")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON."),
    ] = False,
) -> None:
    """Explain rule metadata (deterministic; no AI)."""

    service = create_rule_analysis_service()
    try:
        view = service.inspect_rule(rule_id)
        if not view.production:
            raise RuleApplicationError(
                "Rule not found",
                reason_code="rule_not_found",
                rule_id=rule_id,
            )
        explanation = service.explain_rule_metadata(rule_id)
    except RuleApplicationError as error:
        typer.echo(error.safe_message, err=True)
        raise typer.Exit(code=1) from error
    payload = map_explanation(explanation)
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    typer.echo(f"{payload['subject']}: {payload['message']}")
