"""Read-only Git subprocess execution. Never fetch, checkout, or mutate."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from codestrata.repository_auth.git_runner import build_subprocess_environment, run_git
from codestrata.security.redaction import Redactor

ALLOWED_GIT_COMMANDS = frozenset(
    {
        "cat-file",
        "describe",
        "diff",
        "diff-files",
        "diff-index",
        "diff-tree",
        "for-each-ref",
        "hash-object",
        "log",
        "ls-files",
        "ls-tree",
        "name-rev",
        "rev-list",
        "rev-parse",
        "show",
        "status",
        "symbolic-ref",
        "version",
    }
)

_FORBIDDEN_FLAGS = frozenset(
    {
        "-w",
        "--write",
        "-d",
        "--delete",
        "--upload-pack",
        "--exec",
        "--receive-pack",
    }
)


class ReadOnlyGitError(Exception):
    """A Git command was refused or failed without mutating the checkout."""

    def __init__(self, message: str, *, verb: str | None = None) -> None:
        super().__init__(message)
        self.verb = verb


def git_command_verb(arguments: Sequence[str]) -> str:
    """Return the Git porcelain/plumbing verb from an argument vector."""

    index = 0
    args = list(arguments)
    while index < len(args):
        item = args[index]
        if item in {"-C", "-c"}:
            index += 2
            continue
        if item.startswith("-"):
            index += 1
            continue
        return item
    raise ReadOnlyGitError("Git command verb is missing")


def assert_read_only_git_arguments(arguments: Sequence[str]) -> str:
    """Refuse mutating or network Git verbs before a subprocess starts."""

    verb = git_command_verb(arguments)
    if verb not in ALLOWED_GIT_COMMANDS:
        raise ReadOnlyGitError(
            f"Refused Git command {verb!r}: fetch, checkout, and other mutations are forbidden.",
            verb=verb,
        )
    flags = {item for item in arguments if item.startswith("-")}
    if flags & _FORBIDDEN_FLAGS:
        raise ReadOnlyGitError(
            f"Refused Git command {verb!r} with mutating flag.",
            verb=verb,
        )
    if verb == "hash-object" and "-w" in arguments:
        raise ReadOnlyGitError("hash-object -w would write objects; refused.", verb=verb)
    if verb == "symbolic-ref" and ("-d" in arguments or "--delete" in arguments):
        raise ReadOnlyGitError("symbolic-ref delete is not read-only.", verb=verb)
    return verb


def run_readonly_git(
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float | None = 30,
    environment: Mapping[str, str] | None = None,
    redactor: Redactor | None = None,
) -> str:
    """Run an allow-listed Git command and return stdout. Never mutates cwd."""

    verb = assert_read_only_git_arguments(arguments)
    active = redactor or Redactor()
    env = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GCM_INTERACTIVE": "never",
    }
    if environment:
        env.update(environment)
    try:
        result = run_git(
            arguments,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            environment=env,
            redactor=active,
        )
    except Exception as error:  # noqa: BLE001 - map clone-oriented errors to read-only
        raise ReadOnlyGitError(
            active.redact(f"Read-only Git {verb} failed: {error}"),
            verb=verb,
        ) from error
    return result.stdout or ""


def run_readonly_git_bytes(
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float | None = 30,
    environment: Mapping[str, str] | None = None,
    redactor: Redactor | None = None,
) -> bytes:
    """Run an allow-listed Git command and return raw stdout bytes.

    Used for blob extraction. Never mutates ``cwd``. Does not go through the
    text-mode runner, which would corrupt binary tree objects.
    """

    verb = assert_read_only_git_arguments(arguments)
    active = redactor or Redactor()
    env = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GCM_INTERACTIVE": "never",
    }
    if environment:
        env.update(environment)
    try:
        result = subprocess.run(
            ["git", *arguments],
            check=True,
            capture_output=True,
            text=False,
            shell=False,
            timeout=timeout_seconds,
            env=build_subprocess_environment(env),
            cwd=str(cwd),
        )
    except FileNotFoundError as error:
        raise ReadOnlyGitError(
            active.redact("Read-only Git is not installed or is not available on PATH."),
            verb=verb,
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ReadOnlyGitError(
            active.redact(f"Read-only Git {verb} timed out"),
            verb=verb,
        ) from error
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.decode("utf-8", errors="replace") if error.stderr else ""
        raise ReadOnlyGitError(
            active.redact(f"Read-only Git {verb} failed: {stderr or error}"),
            verb=verb,
        ) from error
    except Exception as error:  # noqa: BLE001 - map clone-oriented errors to read-only
        raise ReadOnlyGitError(
            active.redact(f"Read-only Git {verb} failed: {error}"),
            verb=verb,
        ) from error
    return result.stdout or b""
