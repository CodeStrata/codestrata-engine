"""Utilities for creating and retaining analysis report run directories."""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codestrata.models import AnalysisResult

logger = logging.getLogger(__name__)

_REPORT_RUN_DIRECTORY_PATTERN = re.compile(r"^\d{8}-\d{6}$")
DEFAULT_RETAINED_RUN_COUNT = 3
DEFAULT_ACTIVE_REPORT_RUNS_TO_KEEP = DEFAULT_RETAINED_RUN_COUNT
_DEFAULT_REPORTS_TO_KEEP = DEFAULT_RETAINED_RUN_COUNT
_UNSAFE_REPOSITORY_CHARS = re.compile(r"[^a-z0-9._-]+")


class ReportRetentionError(RuntimeError):
    """Raised when an older report run cannot be pruned safely."""


@dataclass(frozen=True)
class ReportPaths:
    """Paths for all reports generated during one analysis run."""

    directory: Path
    text_report: Path
    json_report: Path
    html_report: Path
    timestamp: str
    repository_name: str

    @property
    def run_directory(self) -> Path:
        """Alias for the timestamped run directory."""

        return self.directory

    @property
    def run_timestamp(self) -> str:
        """Alias for the shared UTC run timestamp."""

        return self.timestamp

    @property
    def html_report_path(self) -> Path:
        return self.html_report

    @property
    def json_report_path(self) -> Path:
        return self.json_report

    @property
    def text_report_path(self) -> Path:
        return self.text_report


def sanitize_repository_directory_name(repository_name: str) -> str:
    """Return a filesystem-safe repository directory name."""

    compact = repository_name.strip().lower()
    slug = _UNSAFE_REPOSITORY_CHARS.sub("-", compact).strip(".-")
    return slug or "repository"


def format_report_run_timestamp(moment: datetime | None = None) -> str:
    """Return a UTC run timestamp formatted as ``YYYYMMDD-HHMMSS``."""

    value = moment if moment is not None else datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.strftime("%Y%m%d-%H%M%S")


def create_report_paths(
    result: AnalysisResult,
    base_directory: Path,
    *,
    timestamp: str | None = None,
    clock: Callable[[], datetime] | None = None,
    create_directory: bool = True,
) -> ReportPaths:
    """Create report paths for one analysis or assessment run.

    Layout:

    ``<base_directory>/<sanitized-repository-name>/<YYYYMMDD-HHMMSS>/``

    Path fields include ``report.html``, ``report.json``, and ``report.txt`` for
    callers such as ``codestrata scan``. Assessment writes only HTML and JSON.

    When ``timestamp`` is provided it is reused for the run directory. Otherwise a
    single UTC timestamp is generated from ``clock`` (or ``datetime.now(UTC)``).
    """

    if timestamp is not None:
        run_timestamp = timestamp
        if not _REPORT_RUN_DIRECTORY_PATTERN.match(run_timestamp):
            raise ValueError(f"timestamp must match YYYYMMDD-HHMMSS, got {run_timestamp!r}")
    else:
        now = clock() if clock is not None else datetime.now(UTC)
        run_timestamp = format_report_run_timestamp(now)

    repository_name = sanitize_repository_directory_name(result.repository.name)
    repository_directory = base_directory / repository_name
    run_directory = repository_directory / run_timestamp

    if create_directory:
        run_directory.mkdir(parents=True, exist_ok=True)

    return ReportPaths(
        directory=run_directory,
        text_report=run_directory / "report.txt",
        json_report=run_directory / "report.json",
        html_report=run_directory / "report.html",
        timestamp=run_timestamp,
        repository_name=repository_name,
    )


def is_completed_report_run(run_directory: Path) -> bool:
    """Return True when a run directory contains required report artifacts.

    Completed runs for both ``codestrata assess`` and ``codestrata scan`` include
    ``report.html`` and ``report.json``. Incomplete or abandoned directories are
    ignored by retention pruning.
    """

    if run_directory.is_symlink() or not run_directory.is_dir():
        return False
    return (run_directory / "report.html").is_file() and (run_directory / "report.json").is_file()


def list_active_report_run_directories(repository_directory: Path) -> list[Path]:
    """Return timestamped run directories, newest first.

    Ignores non-matching names, files, and symlink entries.
    """

    if not repository_directory.exists():
        return []

    candidates: list[Path] = []
    for path in repository_directory.iterdir():
        if path.is_symlink():
            continue
        if path.is_dir() and _REPORT_RUN_DIRECTORY_PATTERN.match(path.name):
            candidates.append(path)
    return sorted(candidates, key=lambda path: path.name, reverse=True)


def list_completed_report_run_directories(repository_directory: Path) -> list[Path]:
    """Return completed timestamped run directories, newest first."""

    return [
        path
        for path in list_active_report_run_directories(repository_directory)
        if is_completed_report_run(path)
    ]


def _is_safe_run_directory(repository_directory: Path, run_directory: Path) -> bool:
    """Return True when ``run_directory`` is a direct child of the repository root."""

    try:
        repository_root = repository_directory.resolve(strict=False)
        candidate = run_directory.resolve(strict=False)
    except OSError:
        return False
    if candidate == repository_root:
        return False
    if candidate.parent != repository_root:
        return False
    if run_directory.is_symlink():
        return False
    return bool(_REPORT_RUN_DIRECTORY_PATTERN.match(run_directory.name))


def retain_recent_reports(
    repository_directory: Path,
    keep: int = DEFAULT_RETAINED_RUN_COUNT,
) -> list[Path]:
    """Keep only the newest completed report-run directories for one repository.

    Older completed runs are deleted in place. No archive directory is created.
    Invalid names, unrelated files, incomplete directories, and symlink escapes are
    ignored. Returns the list of deleted run directories.
    """

    if keep < 1:
        raise ValueError("keep must be at least 1")

    if not repository_directory.exists():
        return []

    completed = list_completed_report_run_directories(repository_directory)
    to_delete = completed[keep:]
    deleted: list[Path] = []
    for outdated_directory in to_delete:
        if not _is_safe_run_directory(repository_directory, outdated_directory):
            logger.warning(
                "Skipping unsafe report run path during retention: %s",
                outdated_directory,
            )
            continue
        try:
            shutil.rmtree(outdated_directory)
        except OSError as error:
            raise ReportRetentionError(
                f"Failed to delete aged report run {outdated_directory.name!r}: {error}"
            ) from error
        logger.info("Removed aged report run %s", outdated_directory.name)
        deleted.append(outdated_directory)
    return deleted


def prune_excess_report_runs(
    repository_directory: Path,
    *,
    keep: int = DEFAULT_RETAINED_RUN_COUNT,
) -> list[Path]:
    """Alias for :func:`retain_recent_reports` used by assessment cleanup."""

    return retain_recent_reports(repository_directory, keep=keep)
