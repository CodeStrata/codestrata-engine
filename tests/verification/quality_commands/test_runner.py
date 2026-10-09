"""Exit-code classification: nonzero is FAIL/BASELINE_FAIL, missing tool is BLOCKED."""

from __future__ import annotations

from pathlib import Path

from verification.quality_commands.manifest import load_manifest
from verification.quality_commands.models import CommandResult, CommandStatus, QualityCommand
from verification.quality_commands.runner import (
    classify_status,
    redact_environ,
    relabel_forbidden,
    run_quality_commands,
)


def _command(command_id: str = "ruff") -> QualityCommand:
    return QualityCommand(
        id=command_id,
        argv=("python", "-m", "ruff", "check", "."),
        required=True,
        timeout_seconds=5,
    )


def test_nonzero_exit_is_fail_not_pass() -> None:
    status = classify_status(
        command=_command(),
        exit_code=1,
        missing_tool=False,
        baseline_ids=set(),
    )
    assert status is CommandStatus.NEW_FAIL
    assert status is not CommandStatus.PASS


def test_baseline_failure_is_not_relabeled_pass() -> None:
    status = classify_status(
        command=_command(),
        exit_code=1,
        missing_tool=False,
        baseline_ids={"ruff"},
    )
    assert status is CommandStatus.BASELINE_FAIL
    assert status is not CommandStatus.PASS


def test_missing_scanner_is_blocked_not_clean() -> None:
    status = classify_status(
        command=_command("pip-audit"),
        exit_code=None,
        missing_tool=True,
        baseline_ids=set(),
    )
    assert status is CommandStatus.BLOCKED


def test_timeout_is_fail() -> None:
    status = classify_status(
        command=_command(),
        exit_code=None,
        missing_tool=False,
        baseline_ids=set(),
    )
    assert status is CommandStatus.BLOCKED


def test_runner_records_true_exit_codes_with_injected_executor(tmp_path: Path) -> None:
    manifest = load_manifest()
    codes = {
        "pip-check": 0,
        "ruff": 1,
        "mypy": 1,
        "pytest-coverage": 2,
        "pip-audit": 127,
    }

    def executor(command: QualityCommand, cwd: Path) -> CommandResult:
        del cwd
        skip = "executable not found" if command.id == "pip-audit" else ""
        return CommandResult(
            id=command.id,
            argv=command.argv,
            exit_code=None if command.id == "pip-audit" else codes[command.id],
            status=CommandStatus.NOT_RUN,
            duration_seconds=0.01,
            stdout_digest="0" * 64,
            stderr_digest="0" * 64,
            skip_reason=skip,
        )

    report = run_quality_commands(
        engine_root=tmp_path,
        manifest=manifest,
        baseline_failure_ids=("ruff", "mypy", "pytest-coverage"),
        executor=executor,
    )
    by_id = {item.id: item for item in report.results}
    assert by_id["pip-check"].status is CommandStatus.PASS
    assert by_id["pip-check"].exit_code == 0
    assert by_id["ruff"].status is CommandStatus.BASELINE_FAIL
    assert by_id["ruff"].exit_code == 1
    assert by_id["mypy"].status is CommandStatus.BASELINE_FAIL
    assert by_id["pytest-coverage"].status is CommandStatus.BASELINE_FAIL
    assert by_id["pytest-coverage"].exit_code == 2
    assert by_id["pip-audit"].status is CommandStatus.BLOCKED
    assert report.merge_ready is False
    assert "ruff" not in report.passing_ids()
    assert relabel_forbidden(report) == ()


def test_cannot_mark_failed_command_as_pass_without_zero_exit() -> None:
    report = run_quality_commands(
        engine_root=Path("."),
        execute=False,
        baseline_failure_ids=("ruff",),
    )
    assert report.ok is False
    for item in report.results:
        assert item.status is CommandStatus.NOT_RUN
        assert item.exit_code is None


def test_redact_drops_publish_credentials() -> None:
    cleaned = redact_environ(
        {
            "PATH": "/usr/bin",
            "PYPI_TOKEN": "pypi-secret",
            "TWINE_PASSWORD": "nope",
            "AWS_SECRET_ACCESS_KEY": "abc",
            "GITHUB_TOKEN": "ghs_x",
        }
    )
    assert cleaned == {"PATH": "/usr/bin"}


def test_new_failure_distinct_from_baseline(tmp_path: Path) -> None:
    manifest = load_manifest()

    def executor(command: QualityCommand, cwd: Path) -> CommandResult:
        del cwd
        code = 0 if command.id != "pip-check" else 1
        return CommandResult(
            id=command.id,
            argv=command.argv,
            exit_code=code,
            status=CommandStatus.NOT_RUN,
            duration_seconds=0.0,
            stdout_digest="0" * 64,
            stderr_digest="0" * 64,
        )

    report = run_quality_commands(
        engine_root=tmp_path,
        manifest=manifest,
        baseline_failure_ids=("ruff",),
        executor=executor,
    )
    by_id = {item.id: item for item in report.results}
    assert by_id["pip-check"].status is CommandStatus.NEW_FAIL
    assert by_id["ruff"].status is CommandStatus.PASS
    assert by_id["ruff"].exit_code == 0
