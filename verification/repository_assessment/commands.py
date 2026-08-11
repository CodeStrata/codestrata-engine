"""CLI command helpers for SV.4 (doctor / init / assess)."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from verification.cli_installation.environment import scrub_environ
from verification.repository_assessment.contract import (
    CANONICAL_ASSESS_ARGS,
    CANONICAL_ASSESS_COMMAND,
    duration_bucket,
)
from verification.repository_assessment.reporting import sanitize_text


@dataclass(frozen=True, slots=True)
class CommandResult:
    name: str
    argv: tuple[str, ...]
    exit_code: int
    duration_seconds: float
    duration_bucket: str
    stdout_sanitized: str
    stderr_sanitized: str
    has_traceback: bool


def assessment_environ(
    base: dict[str, str] | None = None,
    *,
    offline: bool = True,
) -> dict[str, str]:
    """Clean env for assessment: AI off, no provider creds, no telemetry prompts."""

    env = scrub_environ(base)
    # Force non-interactive.
    env["CI"] = "1"
    env["TERM"] = "dumb"
    env.pop("CODESTRATA_TELEMETRY", None)
    env.pop("CODESTRATA_BEDROCK_MODEL_ID", None)
    env.pop("CODESTRATA_OPENAI_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("AWS_ACCESS_KEY_ID", None)
    env.pop("AWS_SECRET_ACCESS_KEY", None)
    env.pop("AWS_SESSION_TOKEN", None)
    if offline:
        # Hint libraries that prefer offline; assess itself must not need network.
        env.setdefault("PIP_NO_INDEX", "1")
    return env


def run_codestrata(
    codestrata: Path,
    args: list[str] | tuple[str, ...],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_s: float = 600.0,
    name: str | None = None,
) -> CommandResult:
    argv = [str(codestrata), *[str(a) for a in args]]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = "command timed out"
    elapsed = time.perf_counter() - started
    combined = f"{stdout}\n{stderr}".lower()
    safe_argv = tuple(
        sanitize_text(part, workspace=cwd) for part in argv[1:]  # omit absolute binary
    )
    return CommandResult(
        name=name or (args[0] if args else "codestrata"),
        argv=safe_argv,
        exit_code=exit_code,
        duration_seconds=elapsed,
        duration_bucket=duration_bucket(elapsed),
        stdout_sanitized=sanitize_text(stdout, workspace=cwd)[:2000],
        stderr_sanitized=sanitize_text(stderr, workspace=cwd)[:2000],
        has_traceback="traceback" in combined or "exception:" in combined,
    )


def run_doctor(codestrata: Path, *, cwd: Path, env: dict[str, str]) -> CommandResult:
    return run_codestrata(codestrata, ["doctor"], cwd=cwd, env=env, name="doctor", timeout_s=120)


def run_init(codestrata: Path, *, cwd: Path, env: dict[str, str]) -> CommandResult:
    return run_codestrata(codestrata, ["init"], cwd=cwd, env=env, name="init", timeout_s=60)


def run_assess(
    codestrata: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    repo: str = ".",
    output: str = "reports",
    extra: list[str] | None = None,
    timeout_s: float = 600.0,
) -> CommandResult:
    args = [
        *CANONICAL_ASSESS_COMMAND,
        "--repo",
        repo,
        "--output",
        output,
        "--no-ai",
    ]
    if extra:
        args.extend(extra)
    # Ensure we never accidentally pass --with-ai.
    if "--with-ai" in args:
        raise ValueError("SV.4 forbids --with-ai")
    return run_codestrata(
        codestrata,
        args,
        cwd=cwd,
        env=env,
        name="assess",
        timeout_s=timeout_s,
    )


def canonical_assess_argv(*, repo: str = ".", output: str = "reports") -> tuple[str, ...]:
    return ("assess", "--repo", repo, "--output", output, "--no-ai")


def assert_no_ai_flag(argv: tuple[str, ...] | list[str]) -> None:
    if "--with-ai" in argv:
        raise AssertionError("assessment must not enable AI")
    # Default contract embeds --no-ai.
    _ = CANONICAL_ASSESS_ARGS
