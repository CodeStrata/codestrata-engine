"""Tests for PMD command construction."""

from pathlib import Path

from codestrata.static_analysis.providers.pmd_command import PmdCommandBuilder


def test_analyze_command_is_argument_list_without_shell() -> None:
    source_root = Path("/tmp/my repo/src/main/java")
    command = PmdCommandBuilder("pmd").analyze_command(
        source_roots=[source_root],
        rulesets=["category/java/bestpractices.xml"],
        report_file=Path("/tmp/report.xml"),
        minimum_priority=5,
    )

    assert command.args[0] == "pmd"
    assert "check" in command.args
    assert "--no-progress" in command.args
    assert "--dir" in command.args
    assert str(source_root.resolve()) in command.args
    assert "--rulesets" in command.args
    assert "category/java/bestpractices.xml" in command.args
    assert "--minimum-priority" in command.args
    assert "LOW" in command.args
    assert all(";" not in arg for arg in command.args)


def test_version_command() -> None:
    command = PmdCommandBuilder("/opt/pmd/bin/pmd").version_command()
    assert command.args == ["/opt/pmd/bin/pmd", "--version"]


def test_legacy_command_joins_source_roots() -> None:
    command = PmdCommandBuilder("pmd").legacy_analyze_command(
        source_roots=[Path("/repo/src/main/java"), Path("/repo/src/test/java")],
        rulesets=["category/java/bestpractices.xml"],
        report_file=Path("/tmp/report.xml"),
        minimum_priority=5,
    )
    assert command.args[1] == "-d"
    assert "src/main/java" in command.args[2]
    assert "src/test/java" in command.args[2]
