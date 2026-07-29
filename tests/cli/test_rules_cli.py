"""CLI tests for codestrata rules (Phase 4.1 / 4.2)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from codestrata.cli import app

runner = CliRunner()


def test_rules_help() -> None:
    result = runner.invoke(app, ["rules", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "inspect" in result.stdout


def test_rules_list_includes_architecture_pack() -> None:
    result = runner.invoke(app, ["rules", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["rules"]
    assert any(
        item["rule_id"] == "architecture.dependency-cycle" for item in payload["rules"]
    )


def test_rules_list_category_architecture() -> None:
    result = runner.invoke(app, ["rules", "list", "--category", "architecture", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload.get("pack", {}).get("pack_id") == "architecture.core"
    assert all(item["category"] == "architecture" for item in payload["rules"])


def test_rules_inspect_architecture_rule() -> None:
    result = runner.invoke(app, ["rules", "inspect", "architecture.dependency-cycle", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["rule_id"] == "architecture.dependency-cycle"
    assert payload["production"] is True


def test_rules_inspect_unknown() -> None:
    result = runner.invoke(app, ["rules", "inspect", "fixture.always-match"])
    assert result.exit_code == 1


def test_assess_still_present() -> None:
    result = runner.invoke(app, ["assess", "--help"])
    assert result.exit_code == 0
    assert "Assess a repository" in result.stdout
