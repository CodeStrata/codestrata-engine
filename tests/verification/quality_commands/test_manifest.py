"""Manifest must list pip-check, ruff, mypy, pytest-coverage, pip-audit."""

from __future__ import annotations

from pathlib import Path

from verification.quality_commands.manifest import REQUIRED_COMMAND_IDS, load_manifest


def test_manifest_declares_required_quality_commands() -> None:
    manifest = load_manifest()
    ids = {command.id for command in manifest.commands}
    assert set(REQUIRED_COMMAND_IDS) <= ids
    assert manifest.coverage.source == "codestrata"
    assert manifest.coverage.branch is True
    assert manifest.coverage.fail_under == 80
    assert manifest.engine_tests_job.name == "engine-tests"
    assert "coverage" in manifest.engine_tests_job.does_not_prove
    assert "ruff" in manifest.engine_tests_job.does_not_prove
    assert "mypy" in manifest.engine_tests_job.does_not_prove
    assert manifest.engine_tests_job.automatic_branch_protection is False
    assert manifest.security_scanner.id == "pip-audit"
    assert manifest.security_scanner.feed_required is True
    assert "BLOCKED" in manifest.security_scanner.severity_policy


def test_manifest_argv_matches_execution_policy() -> None:
    manifest = load_manifest()
    by_id = {command.id: command.argv for command in manifest.commands}
    assert by_id["pip-check"] == ("python", "-m", "pip", "check")
    assert by_id["ruff"] == ("python", "-m", "ruff", "check", ".")
    assert by_id["mypy"] == ("python", "-m", "mypy", "--config-file", "pyproject.toml")
    assert "--cov=codestrata" in by_id["pytest-coverage"]
    assert "--cov-branch" in by_id["pytest-coverage"]
    assert "--cov-fail-under=80" in by_id["pytest-coverage"]
    assert by_id["pip-audit"][:3] == ("python", "-m", "pip_audit")


def test_missing_command_rejected(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "id: broken",
                "version: '0'",
                "coverage: {source: codestrata, branch: true, fail_under: 80}",
                "engine_tests_job:",
                "  name: engine-tests",
                "  workflow: x",
                "  proves: []",
                "  does_not_prove: []",
                "security_scanner:",
                "  id: pip-audit",
                "  module: pip_audit",
                "  argv: [python, -m, pip_audit]",
                "commands:",
                "  - id: pip-check",
                "    argv: [python, -m, pip, check]",
            ]
        ),
        encoding="utf-8",
    )
    try:
        load_manifest(path)
    except ValueError as exc:
        assert "missing required commands" in str(exc)
    else:
        raise AssertionError("expected missing required commands")
