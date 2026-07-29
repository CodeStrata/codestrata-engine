"""CLI rendering for Shared Rule Platform."""

from __future__ import annotations

from typing import Any

import typer


def render_rules_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        typer.echo("No production rules registered (Phase 4.1 platform only).")
        return
    for row in rows:
        typer.echo(
            f"{row['rule_id']}  v{row['version']}  [{row['category']}]  {row['title']}"
        )


def render_rule_detail(row: dict[str, Any]) -> None:
    for key in (
        "rule_id",
        "version",
        "title",
        "description",
        "category",
        "default_severity",
        "enabled_by_default",
        "experimental",
        "requires_enterprise_context",
        "production",
    ):
        typer.echo(f"{key}: {row.get(key)}")
