"""Execute the Engine quality-command manifest and record true exit codes."""

from __future__ import annotations

import hashlib
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from verification.quality_commands.manifest import load_manifest
from verification.quality_commands.models import (
    CommandResult,
    CommandStatus,
    QualityCommand,
    QualityManifest,
    QualityRunReport,
)

CommandExecutor = Callable[[QualityCommand, Path], CommandResult]


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_status(
    *,
    command: QualityCommand,
    exit_code: int | None,
    missing_tool: bool,
    baseline_ids: set[str],
) -> CommandStatus:
    """Map a real exit code onto a status. Missing tools are never PASS."""

    if missing_tool:
        return command.missing_tool_status
    if exit_code is None:
        return CommandStatus.BLOCKED
    if exit_code == 0:
        # A historically failing check that now exits 0 is PASS for this run.
        # It is never rewritten backwards from FAIL to PASS without the exit
        # code actually being 0.
        return CommandStatus.PASS
    if command.id in baseline_ids:
        return CommandStatus.BASELINE_FAIL
    return CommandStatus.NEW_FAIL


def subprocess_executor(command: QualityCommand, cwd: Path) -> CommandResult:
    """Run argv as-is. Keep the exit code; only store SHA-256 of stdout/stderr."""
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command.argv),
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
            timeout=command.timeout_seconds,
        )
    except FileNotFoundError:
        return CommandResult(
            id=command.id,
            argv=command.argv,
            exit_code=None,
            status=command.missing_tool_status,
            duration_seconds=time.perf_counter() - started,
            stdout_digest=digest_text(""),
            stderr_digest=digest_text(""),
            skip_reason="executable not found",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or "timeout"
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return CommandResult(
            id=command.id,
            argv=command.argv,
            exit_code=None,
            status=CommandStatus.FAIL,
            duration_seconds=time.perf_counter() - started,
            stdout_digest=digest_text(stdout),
            stderr_digest=digest_text(stderr),
            skip_reason=f"timeout after {command.timeout_seconds}s",
        )
    skip_reason = ""
    stderr = completed.stderr or ""
    if completed.returncode != 0 and "No module named" in stderr:
        skip_reason = "executable not found"
    return CommandResult(
        id=command.id,
        argv=command.argv,
        exit_code=completed.returncode,
        status=CommandStatus.NOT_RUN,
        duration_seconds=time.perf_counter() - started,
        stdout_digest=digest_text(completed.stdout or ""),
        stderr_digest=digest_text(stderr),
        skip_reason=skip_reason,
    )


def run_quality_commands(
    *,
    engine_root: Path,
    manifest: QualityManifest | None = None,
    baseline_failure_ids: tuple[str, ...] = (),
    executor: CommandExecutor | None = None,
    execute: bool = True,
) -> QualityRunReport:
    """Run each manifest command and classify it.

    ``baseline_failure_ids`` (from G00) only change FAIL into BASELINE_FAIL.
    They cannot turn a nonzero exit into PASS. merge_ready is true only when
    every required command actually PASSed.
    """
    loaded = manifest or load_manifest()
    baseline = set(baseline_failure_ids)
    execute_fn = executor or subprocess_executor
    results: list[CommandResult] = []
    notes = [
        loaded.baseline_notes.strip(),
        (
            f"engine-tests job '{loaded.engine_tests_job.name}' proves "
            f"{', '.join(loaded.engine_tests_job.proves) or 'nothing'}; "
            "it is not evidence of lint/type/coverage"
        ),
        (
            "reviewer checkpoint is required; this manifest is not an automatic "
            "branch-protection rule"
        ),
    ]
    # Dry-run validates the manifest but must not look like a passing gate.
    if not execute:
        notes.append("execute=false; commands were not run")
        placeholder = tuple(
            CommandResult(
                id=command.id,
                argv=command.argv,
                exit_code=None,
                status=CommandStatus.NOT_RUN,
                duration_seconds=0.0,
                stdout_digest=digest_text(""),
                stderr_digest=digest_text(""),
                skip_reason="execute=false",
            )
            for command in loaded.commands
        )
        return QualityRunReport(
            ok=False,
            merge_ready=False,
            results=placeholder,
            baseline_failure_ids=tuple(sorted(baseline)),
            notes=tuple(item for item in notes if item),
        )

    for command in loaded.commands:
        raw = execute_fn(command, engine_root)
        missing = raw.skip_reason == "executable not found" or (
            raw.exit_code in {127, 2} and "No module named" in raw.skip_reason
        )
        status = classify_status(
            command=command,
            exit_code=raw.exit_code,
            missing_tool=missing,
            baseline_ids=baseline,
        )
        if status is CommandStatus.PASS and command.id in baseline:
            # Exit 0 is allowed to leave the baseline list for this run, but the
            # recorded historical baseline file is not rewritten here.
            notes.append(
                f"{command.id} exited 0; historical baseline failure is not "
                "relabeled in this report"
            )
        results.append(
            CommandResult(
                id=raw.id,
                argv=raw.argv,
                exit_code=raw.exit_code,
                status=status,
                duration_seconds=raw.duration_seconds,
                stdout_digest=raw.stdout_digest,
                stderr_digest=raw.stderr_digest,
                skip_reason=raw.skip_reason,
            )
        )

    blocking = {
        CommandStatus.FAIL,
        CommandStatus.NEW_FAIL,
        CommandStatus.BASELINE_FAIL,
        CommandStatus.BLOCKED,
        CommandStatus.NOT_RUN,
    }
    required_ids = {command.id: command.required for command in loaded.commands}
    required_failed = [
        item for item in results if item.status in blocking and required_ids[item.id]
    ]
    merge_ready = not required_failed
    # A run can be "ok" only when every required command PASSed. Baseline
    # failures keep merge_ready false.
    return QualityRunReport(
        ok=merge_ready,
        merge_ready=merge_ready,
        results=tuple(results),
        baseline_failure_ids=tuple(sorted(baseline)),
        notes=tuple(item for item in notes if item),
    )


def relabel_forbidden(report: QualityRunReport) -> tuple[str, ...]:
    """IDs that a caller tried to treat as PASS while still in the baseline set
    without an actual zero exit code."""

    forbidden: list[str] = []
    baseline = set(report.baseline_failure_ids)
    for item in report.results:
        if item.id in baseline and item.status is CommandStatus.PASS and item.exit_code != 0:
            forbidden.append(item.id)
        if item.status is CommandStatus.PASS and item.exit_code not in {0}:
            forbidden.append(item.id)
    return tuple(forbidden)


def redact_environ(environ: Mapping[str, str]) -> dict[str, str]:
    """Drop known publish/credential keys so quality logs stay non-secret."""

    blocked_fragments = (
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "CREDENTIAL",
        "AWS_SECRET",
        "PYPI",
        "TWINE",
        "NPM_",
        "OIDC",
    )
    cleaned: dict[str, str] = {}
    for key, value in environ.items():
        upper = key.upper()
        if any(fragment in upper for fragment in blocked_fragments):
            continue
        cleaned[key] = value
    return cleaned
