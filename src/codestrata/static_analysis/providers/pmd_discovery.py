"""PMD executable discovery and validation."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CODESTRATA_PMD_PATH_ENV = "CODESTRATA_PMD_PATH"
DEFAULT_VERSION_TIMEOUT_SECONDS = 15

_HOMEBREW_CANDIDATES = (
    Path("/opt/homebrew/bin/pmd"),
    Path("/usr/local/bin/pmd"),
    Path("/opt/homebrew/bin/pmd-bin"),
    Path("/usr/local/bin/pmd-bin"),
)

_PATH_NAMES = ("pmd", "pmd-bin")


@dataclass(frozen=True)
class PmdDiscoveryResult:
    """Result of resolving a PMD executable candidate."""

    executable: str | None
    source: str
    version: str | None = None
    message: str | None = None


def resolve_pmd_executable(
    *,
    cli_path: str | None = None,
    configured: str | None = None,
    env: Mapping[str, str] | None = None,
    path_lookup: Callable[[str], str | None] | None = None,
    platform: str | None = None,
    filesystem_exists: Callable[[Path], bool] | None = None,
    is_file: Callable[[Path], bool] | None = None,
    is_executable: Callable[[Path], bool] | None = None,
) -> PmdDiscoveryResult:
    """Resolve PMD executable using CLI → env → config → PATH → Homebrew order."""

    environment = env if env is not None else os.environ
    which = path_lookup or shutil.which
    exists = filesystem_exists or (lambda path: path.exists())
    file_check = is_file or (lambda path: path.is_file())
    exec_check = is_executable or _path_is_executable
    current_platform = platform if platform is not None else sys.platform

    candidates: list[tuple[str, str]] = []

    if cli_path and cli_path.strip():
        candidates.append((cli_path.strip(), "cli"))

    env_path = environment.get(CODESTRATA_PMD_PATH_ENV)
    if env_path and env_path.strip():
        candidates.append((env_path.strip(), "environment"))

    if configured and configured.strip():
        compact = configured.strip()
        if _looks_like_path(compact):
            candidates.append((compact, "config"))
        else:
            resolved = which(compact)
            if resolved:
                candidates.append((resolved, "config"))
            else:
                candidates.append((compact, "config"))

    for name in _PATH_NAMES:
        resolved = which(name)
        if resolved:
            candidates.append((resolved, "path"))

    if current_platform == "darwin":
        for homebrew_path in _HOMEBREW_CANDIDATES:
            candidates.append((str(homebrew_path), "homebrew"))

    seen: set[str] = set()
    for candidate_path, source in candidates:
        if candidate_path in seen:
            continue
        seen.add(candidate_path)
        path = Path(candidate_path)
        if _looks_like_path(candidate_path) or path.is_absolute():
            if not exists(path):
                if source in {"cli", "environment", "config"}:
                    return PmdDiscoveryResult(
                        executable=None,
                        source=source,
                        message="Configured PMD executable path was not found.",
                    )
                continue
            if not file_check(path):
                return PmdDiscoveryResult(
                    executable=None,
                    source=source,
                    message="Configured PMD path exists but is not a file.",
                )
            if not exec_check(path):
                return PmdDiscoveryResult(
                    executable=None,
                    source=source,
                    message="Configured PMD path exists but is not executable.",
                )
            return PmdDiscoveryResult(executable=str(path), source=source)

        # Bare command names are accepted for version probing.
        resolved_name = which(candidate_path)
        return PmdDiscoveryResult(
            executable=resolved_name or candidate_path,
            source=source,
        )

    return PmdDiscoveryResult(
        executable=None,
        source="none",
        message="PMD executable was not found or could not report a version.",
    )


def probe_pmd_version(
    executable: str,
    *,
    process_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    timeout_seconds: int = DEFAULT_VERSION_TIMEOUT_SECONDS,
) -> str | None:
    """Run a lightweight PMD version probe and return a sanitized version string."""

    runner = process_runner or subprocess.run
    try:
        completed = runner(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return None

    if not isinstance(completed, subprocess.CompletedProcess):
        raise TypeError("process runner must return CompletedProcess")

    output = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", output)
    if match is not None:
        return match.group(1)
    if completed.returncode == 0:
        return "unknown"
    return None


def sanitize_pmd_user_message(message: str) -> str:
    """Return a user-facing message without absolute filesystem paths."""

    compact = " ".join(message.split())
    # Drop absolute POSIX and Windows-style paths.
    without_posix = re.sub(r"(?<!\w)/(?:[^/\s]+/)+[^/\s]+", "<path>", compact)
    without_windows = re.sub(
        r"(?<!\w)[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s]+",
        "<path>",
        without_posix,
    )
    if len(without_windows) > 300:
        return without_windows[:297] + "..."
    return without_windows


def _looks_like_path(value: str) -> bool:
    return (
        value.startswith("/")
        or value.startswith("./")
        or value.startswith("../")
        or "\\" in value
        or (len(value) >= 3 and value[1] == ":" and value[2] in {"\\", "/"})
    )


def _path_is_executable(path: Path) -> bool:
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def discovery_diagnostic_lines(result: PmdDiscoveryResult) -> Sequence[str]:
    """Return verbose diagnostic lines without absolute executable paths."""

    lines = [f"PMD discovery source: {result.source}"]
    if result.executable is not None:
        lines.append(f"PMD executable name: {Path(result.executable).name}")
    if result.version is not None:
        lines.append(f"PMD version: {result.version}")
    if result.message:
        lines.append(sanitize_pmd_user_message(result.message))
    return lines
