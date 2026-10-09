"""E11.1 Community CLI contract fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codestrata.cli import app
from codestrata.cli.community_contract import (
    BUNDLED_CATALOG_ID,
    SUPPORTED_RULE_COMMANDS,
    UNSUPPORTED_RULE_COMMANDS,
    bundled_catalog_validated,
    collection_opt_in_required,
    live_command_compatibility,
    reject_custom_rule_command,
)
from codestrata.cli.doctor import run_doctor_checks
from codestrata.cli.init_cmd import MINIMAL_CODESTRATA_TOML, write_minimal_config
from codestrata.cli.rules import rules_app

runner = CliRunner()


def test_assess_does_not_require_collection_opt_in() -> None:
    assert collection_opt_in_required("assess") is False
    help_text = runner.invoke(app, ["assess", "--help"])
    assert help_text.exit_code == 0
    combined = help_text.stdout + help_text.stderr
    assert "--no-ai" in combined
    assert "login" not in combined.lower()


def test_live_command_map_includes_primary_commands() -> None:
    mapped = live_command_compatibility(app)
    for name in ("init", "doctor", "assess", "compare", "trend"):
        assert name in mapped
        assert mapped[name]["exit_success"] == 0
        assert mapped[name]["exit_usage"] == 2
    assert bundled_catalog_validated() is True


def test_doctor_lists_capabilities_trust_and_config(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    write_minimal_config(config)
    checks = run_doctor_checks(config_path=config, output_directory=tmp_path / "reports")
    by_name = {item.name: item for item in checks}
    assert by_name["capabilities"].ok is True
    assert "Cloud setup is not required" in by_name["capabilities"].detail
    assert "trend --repo" in by_name["capabilities"].detail
    assert by_name["trust"].ok is True
    assert BUNDLED_CATALOG_ID in by_name["trust"].detail
    assert by_name["config"].ok is True
    assert "No login is required" in by_name["config"].detail


def test_init_documents_parameters_exclusions_and_migration() -> None:
    text = MINIMAL_CODESTRATA_TOML
    assert "max_cycle_length" in text
    assert "[knowledge]" in text
    assert "Suppressions" in text
    assert "assess --repo" in text


def test_rules_help_hides_custom_rule_authoring() -> None:
    result = runner.invoke(app, ["rules", "--help"])
    assert result.exit_code == 0
    registered = {command.name for command in rules_app.registered_commands}
    assert set(SUPPORTED_RULE_COMMANDS) <= registered
    assert registered.isdisjoint(UNSUPPORTED_RULE_COMMANDS)
    for name in UNSUPPORTED_RULE_COMMANDS:
        assert reject_custom_rule_command(name)
        blocked = runner.invoke(app, ["rules", name])
        assert blocked.exit_code != 0


def test_compare_requires_explicit_files(tmp_path: Path) -> None:
    missing = runner.invoke(
        app,
        [
            "compare",
            "--baseline",
            str(tmp_path / "missing-base.json"),
            "--candidate",
            str(tmp_path / "missing-cand.json"),
        ],
    )
    assert missing.exit_code == 2
    assert "not found" in (missing.stdout + missing.stderr)

    partial = tmp_path / "partial.json"
    partial.write_text("{", encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"not": "a report"}), encoding="utf-8")
    failed = runner.invoke(
        app,
        ["compare", "--baseline", str(partial), "--candidate", str(other)],
    )
    assert failed.exit_code == 1


def test_p10_trend_is_fixed_five_and_custom_rules_stay_blocked() -> None:
    help_result = runner.invoke(app, ["trend", "--help"])
    assert help_result.exit_code == 0
    text = help_result.stdout + help_result.stderr
    assert "--repo" in text
    assert "--max-count" not in text
    assert "--series" not in text
    assert "create" not in {command.name for command in rules_app.registered_commands}
    for name in UNSUPPORTED_RULE_COMMANDS:
        assert reject_custom_rule_command(name)


def test_compare_help_has_no_hidden_baseline() -> None:
    result = runner.invoke(app, ["compare", "--help"])
    assert result.exit_code == 0
    text = result.stdout + result.stderr
    assert "--baseline" in text
    assert "--candidate" in text
    assert "hidden" in text.lower()
    assert "--series" not in text
    assert "--slot" not in text
    assert "s1-s2" not in text
