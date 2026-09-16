"""Load and execute the Engine-owned quality-command manifest.

The YAML file ``quality-commands.yaml`` is the source of truth. Suites:

* ``harness``  — ruff/mypy/pytest for *this* package (must PASS)
* ``product``  — G00 root commands; failures are BASELINE_FAIL, not a new pass
* ``security`` — pip-audit; missing tool/feed is BLOCKED, never a fake clean

``record_as_baseline`` is what stops a known product failure from being
relabeled as success. Publish tokens are stripped from the subprocess env.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Never forward production publish credentials into quality subprocesses.
PUBLISH_ENV_DENYLIST = (
    "PYPI_TOKEN",
    "PYPI_PASSWORD",
    "TWINE_PASSWORD",
    "TWINE_USERNAME",
    "TWINE_REPOSITORY_URL",
    "NPM_TOKEN",
    "OIDC_TOKEN",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)


@dataclass(frozen=True)
class QualityCommand:
    id: str
    argv: tuple[str, ...]
    suite: str
    cwd: str
    record_as_baseline: bool
    notes: str
    optional: bool


@dataclass(frozen=True)
class QualityManifest:
    schema_version: int
    package_revision: str
    working_directory: str
    coverage_source: str
    coverage_floor: int
    branch_measurement: bool
    security_scanner: dict[str, Any]
    commands: tuple[QualityCommand, ...]
    engine_tests_job: dict[str, Any]


@dataclass(frozen=True)
class CommandResult:
    command: QualityCommand
    exit_code: int
    status: str
    stdout_tail: str
    stderr_tail: str


def load_manifest(path: Path) -> QualityManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("quality-command manifest must be a mapping")
    commands = tuple(
        QualityCommand(
            id=str(item["id"]),
            argv=tuple(str(part) for part in item["argv"]),
            suite=str(item["suite"]),
            cwd=str(item.get("cwd", "repository_root")),
            record_as_baseline=bool(item.get("record_as_baseline", False)),
            notes=str(item.get("notes", "")),
            optional=bool(item.get("optional", False)),
        )
        for item in raw["commands"]
    )
    return QualityManifest(
        schema_version=int(raw["schema_version"]),
        package_revision=str(raw["package_revision"]),
        working_directory=str(raw["working_directory"]),
        coverage_source=str(raw["coverage_source"]),
        coverage_floor=int(raw["coverage_floor"]),
        branch_measurement=bool(raw["branch_measurement"]),
        security_scanner=dict(raw["security_scanner"]),
        commands=commands,
        engine_tests_job=dict(raw["engine_tests_job"]),
    )


def _sanitize_env(env: dict[str, str]) -> dict[str, str]:
    cleaned = dict(env)
    for key in PUBLISH_ENV_DENYLIST:
        cleaned.pop(key, None)
    return cleaned


def _cwd_for(command: QualityCommand, repo_root: Path) -> Path:
    if command.cwd == "engine":
        return repo_root / "engine"
    return repo_root


def _classify(command: QualityCommand, exit_code: int, missing: bool) -> str:
    """Map a process result. Missing tools are BLOCKED; known product gaps are BASELINE_FAIL."""
    if missing:
        return "BLOCKED"
    if exit_code == 0:
        return "PASS"
    if command.record_as_baseline:
        return "BASELINE_FAIL"
    return "FAIL"


def run_command(
    command: QualityCommand,
    repo_root: Path,
    *,
    env: dict[str, str] | None = None,
    timeout_s: int = 3600,
) -> CommandResult:
    runtime_env = _sanitize_env(env if env is not None else dict(os.environ))
    try:
        completed = subprocess.run(
            list(command.argv),
            cwd=_cwd_for(command, repo_root),
            check=False,
            capture_output=True,
            text=True,
            env=runtime_env,
            timeout=timeout_s,
        )
    except FileNotFoundError:
        return CommandResult(
            command=command,
            exit_code=127,
            status="BLOCKED",
            stdout_tail="",
            stderr_tail=f"executable not found: {command.argv[0]}",
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            command=command,
            exit_code=124,
            status="FAIL",
            stdout_tail="",
            stderr_tail=f"timed out after {timeout_s}s",
        )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = f"{stdout}\n{stderr}"
    missing_module = "No module named" in combined
    status = _classify(command, completed.returncode, missing=missing_module)
    if missing_module and command.optional:
        status = "BLOCKED"
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        status=status,
        stdout_tail=stdout[-2000:],
        stderr_tail=stderr[-2000:],
    )


def run_suite(
    manifest: QualityManifest,
    repo_root: Path,
    *,
    suite: str,
    env: dict[str, str] | None = None,
) -> tuple[CommandResult, ...]:
    selected = tuple(cmd for cmd in manifest.commands if cmd.suite == suite)
    return tuple(run_command(cmd, repo_root, env=env) for cmd in selected)


def overall_status(results: tuple[CommandResult, ...]) -> str:
    # Worst result wins: blocked/fail before a mix of baseline fails and passes.
    if any(result.status == "BLOCKED" for result in results):
        return "BLOCKED"
    if any(result.status == "FAIL" for result in results):
        return "FAIL"
    if any(result.status == "BASELINE_FAIL" for result in results):
        return "BASELINE_FAIL"
    if results and all(result.status == "PASS" for result in results):
        return "PASS"
    return "ERROR"


# CLI: python -m verification quality --suite harness|product|security
# Manifest: quality-commands.yaml in this directory.
